"""Deterministic screening plus Gemini prompt-ranking orchestration.

No vector, embedding, cosine, or nearest-neighbor retrieval is used here.  The
only model call is the server-side structured Gemini boundary in ``gemini.py``.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from src.grants import config as C
from src.grants.gemini import GeminiRankingError, RankingClient, validate_rankings
from src.grants.normalize import is_healthcare_relevant, is_open_or_forecasted, normalized_document

GEOGRAPHIC_EXCLUSION_TERMS = (
    "guam", "american samoa", "northern mariana", "u.s. virgin islands", "puerto rico",
    "senegal", "ethiopia", "central america", "mississippi delta region",
)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _days_remaining(opportunity: dict[str, Any], today: date) -> int | None:
    closing = opportunity.get("closing_date")
    return (date.fromisoformat(closing) - today).days if closing else None


def screen_eligibility(opportunity: dict[str, Any], *, today: date) -> tuple[str, str | None]:
    """Return restrained compatibility categories, never a legal conclusion."""
    if not is_open_or_forecasted(opportunity, today=today):
        return "Likely incompatible", "The opportunity is closed, archived, or past its stated deadline."
    text = " ".join((opportunity.get("title") or "", opportunity.get("eligibility_description") or "", opportunity.get("description") or "")).lower()
    if any(term in text for term in GEOGRAPHIC_EXCLUSION_TERMS) and "virginia" not in text:
        return "Likely incompatible", "The published eligibility language names a geography that does not include Virginia."
    applicant_types = " ".join(opportunity.get("applicant_types") or []).lower()
    if applicant_types and "individual" in applicant_types and not any(word in applicant_types for word in ("nonprofit", "government", "organization", "unrestricted")):
        return "Likely incompatible", "The structured applicant types are limited to individuals rather than organizations."
    if any(word in applicant_types for word in ("nonprofit", "government", "unrestricted", "organization")):
        return "Likely compatible", "The structured applicant types include organization categories commonly used by clinics or their partners."
    return "Needs verification", "The clinic's legal organization type and the full applicant requirements must be confirmed."


def candidate_opportunities(opportunities: list[dict[str, Any]], *, today: date) -> list[dict[str, Any]]:
    return [item for item in opportunities if is_open_or_forecasted(item, today=today) and is_healthcare_relevant(item) and screen_eligibility(item, today=today)[0] != "Likely incompatible"]


def candidate_prefilter(profile: dict[str, Any], opportunities: list[dict[str, Any]], *, limit: int = C.GEMINI_CANDIDATE_LIMIT) -> list[dict[str, Any]]:
    """Transparent controlled-vocabulary candidate selection before Gemini.

    Opportunity text is only checked for exact controlled terms.  This bounded
    shortlist keeps API cost predictable without pretending to be semantic ML.
    """
    tags = [str(tag.get("tag")) for tag in profile.get("profileTags") or []]
    rows = []
    for item in opportunities:
        text = normalized_document(item).lower()
        hits = [(tag, term) for tag in tags for term in C.PREFILTER_TERMS.get(tag, ()) if term in text]
        health = any(str(category).lower() == "health" for category in item.get("funding_categories") or [])
        rows.append((len(hits) + (1 if health else 0), str(item["opportunity_id"]), item))
    # Retain a limited fallback corpus even when the county has no activated tags.
    return [item for _, _, item in sorted(rows, key=lambda row: (-row[0], row[1]))[:limit]]


def _deadline_score(opportunity: dict[str, Any], today: date) -> tuple[float, str, int | None]:
    days = _days_remaining(opportunity, today)
    if days is None:
        return 0.6, "Forecast - deadline not provided" if opportunity.get("status") == "forecasted" else "Open - deadline not provided", None
    if days < 0:
        return 0.0, "Deadline passed", days
    return _clamp(0.5 + min(days, 90) / 180), "Open", days


def _eligibility_score(status: str) -> float:
    return {"Likely compatible": 0.8, "Needs verification": 0.5, "Likely incompatible": 0.0}[status]


def _tier(score: float) -> str:
    return "Strong relevance" if score >= .70 else "Moderate relevance" if score >= .45 else "Limited relevance"


def readiness_checklist(opportunity: dict[str, Any]) -> list[str]:
    checks = ["Confirm organization type and the full published eligibility requirements.", "Confirm UEI and SAM.gov registration status.", "Define the project scope, target population, and implementation partners.", "Estimate a budget and confirm required attachments."]
    if opportunity.get("cost_sharing_required") is True:
        checks.insert(2, "Confirm the ability to meet the stated cost-sharing requirement.")
    return checks[:5]


def _decorate(match: dict[str, Any], opportunity: dict[str, Any], *, today: date) -> dict[str, Any]:
    eligibility, eligibility_reason = screen_eligibility(opportunity, today=today)
    deadline_score, deadline_status, days = _deadline_score(opportunity, today)
    gemini_score = _clamp(float(match["geminiScore"]))
    score = _clamp(C.SCORE_WEIGHTS["gemini"] * gemini_score + C.SCORE_WEIGHTS["eligibility"] * _eligibility_score(eligibility) + C.SCORE_WEIGHTS["deadline"] * deadline_score)
    tags = [tag for tag in match.get("matchedTags", []) if tag]
    reasons = [str(match["geminiRationale"])]
    if tags:
        reasons.append("Gemini cited county planning tags: " + ", ".join(tags[:3]) + ".")
    if deadline_status == "Open" and opportunity.get("closing_date"):
        reasons.append(f"The listed application deadline is {opportunity['closing_date']}.")
    return {"opportunityId": opportunity["opportunity_id"], "matchScore": round(score, 4), "geminiScore": round(gemini_score, 4), "eligibilityScore": round(_eligibility_score(eligibility), 4), "deadlineScore": round(deadline_score, 4), "eligibilityStatus": eligibility, "eligibilityScreenReason": eligibility_reason, "deadlineStatus": deadline_status, "daysRemaining": days, "matchTier": _tier(score), "fitReasons": reasons[:3], "matchedTags": tags, "readinessChecklist": readiness_checklist(opportunity)}


def rank_profiles(profiles: dict[str, dict[str, Any]], opportunities: list[dict[str, Any]], *, ranker: RankingClient, today: date) -> dict[str, list[dict[str, Any]]]:
    """Batch county profiles through Gemini and validate its IDs server-side."""
    output = {fips: [] for fips in profiles}
    for start in range(0, len(profiles), C.GEMINI_PROFILE_BATCH_SIZE):
        batch = list(profiles.values())[start:start + C.GEMINI_PROFILE_BATCH_SIZE]
        allowed_by_fips = {profile["countyFips"]: candidate_prefilter(profile, opportunities) for profile in batch}
        candidates = {item["opportunity_id"]: item for rows in allowed_by_fips.values() for item in rows}
        validated = validate_rankings(ranker.rank(batch, list(candidates.values())), batch, candidates.values())
        for profile in batch:
            allowed = {item["opportunity_id"] for item in allowed_by_fips[profile["countyFips"]]}
            output[profile["countyFips"]] = sorted((_decorate(match, candidates[match["opportunityId"]], today=today) for match in validated[profile["countyFips"]] if match["opportunityId"] in allowed), key=lambda item: (-item["matchScore"], item["opportunityId"]))[:C.TOP_RECOMMENDATIONS]
    return output


def evaluation_metrics(opportunities: list[dict[str, Any]], candidates: list[dict[str, Any]], matches_by_county: dict[str, list[dict[str, Any]]], *, today: date) -> dict[str, Any]:
    all_matches = [match for matches in matches_by_county.values() for match in matches]
    agency = {item["opportunity_id"]: item.get("agency_code") or "Unknown" for item in candidates}
    categories = {item["opportunity_id"]: item.get("funding_categories") or [] for item in candidates}
    total = len(opportunities) or 1
    return {"validOpportunityRate": sum(bool(item.get("opportunity_id") and item.get("title")) for item in opportunities) / total, "openDeadlineRate": sum(is_open_or_forecasted(item, today=today) for item in opportunities) / total, "healthcareRelevanceFilteringRate": len(candidates) / total, "opportunityCoverage": len({match["opportunityId"] for match in all_matches}) / max(len(candidates), 1), "countyRecommendationCoverage": sum(bool(matches) for matches in matches_by_county.values()) / max(len(matches_by_county), 1), "duplicateRecommendationRate": 1 - len({(county, match["opportunityId"]) for county, matches in matches_by_county.items() for match in matches}) / max(len(all_matches), 1), "recommendationAgencyDiversity": len({agency.get(match["opportunityId"]) for match in all_matches}), "recommendationCategoryDiversity": len({category for match in all_matches for category in categories.get(match["opportunityId"], [])}), "nonemptyExplanationRate": sum(bool(match.get("fitReasons")) for match in all_matches) / max(len(all_matches), 1), "officialLinkValidityRate": sum(item.get("official_url", "").startswith("https://www.grants.gov/") for item in candidates) / max(len(candidates), 1)}
