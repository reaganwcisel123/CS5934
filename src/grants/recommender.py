"""Content-based rural clinic grant recommender using TF-IDF + cosine neighbors."""

from __future__ import annotations

from collections import Counter
from datetime import date
import json
from pathlib import Path
from typing import Any

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

from src.grants import config as C
from src.grants.normalize import is_healthcare_relevant, is_open_or_forecasted, normalized_document

TAG_TERMS = {
    "rural_healthcare_delivery": ("rural", "health care", "healthcare"),
    "primary_care_workforce_shortage": ("primary care", "workforce", "recruitment", "retention"),
    "behavioral_health_access": ("behavioral health", "mental health", "substance use"),
    "mental_health_services": ("mental health", "behavioral health"),
    "diabetes_prevention_and_management": ("diabetes", "chronic disease"),
    "hypertension_management": ("hypertension", "blood pressure", "cardiovascular"),
    "obesity_prevention": ("obesity", "nutrition", "physical activity"),
    "food_access": ("food access", "food insecurity", "nutrition"),
    "care_coordination": ("care coordination", "care access", "access to care", "navigation"),
    "community_outreach": ("community outreach", "community health", "outreach"),
    "health_equity": ("health equity", "health disparities", "underserved"),
    "clinic_infrastructure": ("infrastructure", "facility", "equipment"),
    "quality_improvement": ("quality improvement", "quality of care"),
}
# These terms describe publisher-stated program areas that are clearly outside
# Virginia. They are intentionally used only as hard exclusions when the
# opportunity text does not also name Virginia.
GEOGRAPHIC_EXCLUSION_TERMS = (
    "guam", "american samoa", "northern mariana", "u.s. virgin islands", "puerto rico",
    "senegal", "ethiopia", "central america", "mississippi delta region",
)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _days_remaining(opportunity: dict[str, Any], today: date) -> int | None:
    closing = opportunity.get("closing_date")
    if not closing:
        return None
    return (date.fromisoformat(closing) - today).days


def screen_eligibility(opportunity: dict[str, Any], *, today: date) -> tuple[str, str | None]:
    """Return a restrained compatibility screen, never a legal eligibility claim."""
    if not is_open_or_forecasted(opportunity, today=today):
        return "Likely incompatible", "The opportunity is closed, archived, or past its stated deadline."
    text = " ".join((
        opportunity.get("title") or "", opportunity.get("eligibility_description") or "", opportunity.get("description") or "",
    )).lower()
    if any(term in text for term in GEOGRAPHIC_EXCLUSION_TERMS) and "virginia" not in text:
        return "Likely incompatible", "The published eligibility language names a geography that does not include Virginia."
    applicant_types = " ".join(opportunity.get("applicant_types") or []).lower()
    if applicant_types and "individual" in applicant_types and not any(word in applicant_types for word in ("nonprofit", "government", "organization", "unrestricted")):
        return "Likely incompatible", "The structured applicant types are limited to individuals rather than organizations."
    if any(word in applicant_types for word in ("nonprofit", "government", "unrestricted", "organization")):
        return "Likely compatible", "The structured applicant types include organization categories commonly used by clinics or their partners."
    return "Needs verification", "The clinic's legal organization type and the full applicant requirements must be confirmed."


def candidate_opportunities(opportunities: list[dict[str, Any]], *, today: date) -> list[dict[str, Any]]:
    """Retain active, healthcare-relevant records and hard-exclude clear mismatches."""
    candidates = []
    for opportunity in opportunities:
        status, _ = screen_eligibility(opportunity, today=today)
        if is_open_or_forecasted(opportunity, today=today) and is_healthcare_relevant(opportunity) and status != "Likely incompatible":
            candidates.append(opportunity)
    return candidates


def _category_alignment(profile: dict[str, Any], opportunity: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    document = normalized_document(opportunity).lower()
    evidence = []
    for tag in profile.get("profileTags") or []:
        terms = TAG_TERMS.get(tag["tag"], ())
        matched = next((term for term in terms if term in document), None)
        if matched:
            evidence.append({"tag": tag["tag"], "label": tag["label"], "term": matched})
    health_category = any(category.lower() == "health" for category in opportunity.get("funding_categories") or [])
    tag_share = len(evidence) / max(len(profile.get("profileTags") or []), 1)
    return _clamp((0.4 if health_category else 0.0) + 0.6 * tag_share), evidence


def _deadline_score(opportunity: dict[str, Any], today: date) -> tuple[float, str, int | None]:
    days = _days_remaining(opportunity, today)
    if days is None:
        status = "Forecast — deadline not provided" if opportunity.get("status") == "forecasted" else "Open — deadline not provided"
        return 0.6, status, None
    if days < 0:
        return 0.0, "Deadline passed", days
    return _clamp(0.5 + min(days, 90) / 180), "Open", days


def _eligibility_score(status: str) -> float:
    return {"Likely compatible": 0.8, "Needs verification": 0.5, "Likely incompatible": 0.0}[status]


def _match_tier(score: float) -> str:
    return "Strong relevance" if score >= 0.70 else "Moderate relevance" if score >= 0.45 else "Limited relevance"


def _fit_reasons(opportunity: dict[str, Any], evidence: list[dict[str, Any]], deadline_status: str) -> list[str]:
    document = normalized_document(opportunity).lower()
    reasons: list[str] = []
    if "rural" in document:
        reasons.append("Explicitly references rural communities or rural health delivery.")
    for item in evidence:
        reasons.append(f"References {item['term']}, aligning with the county-informed priority: {item['label']}.")
    if any(category.lower() == "health" for category in opportunity.get("funding_categories") or []):
        reasons.append("The published funding category includes Health.")
    if deadline_status == "Open" and opportunity.get("closing_date"):
        reasons.append(f"The listed application deadline is {opportunity['closing_date']}.")
    if not reasons:
        reasons.append("The opportunity remains in the active healthcare-relevant corpus.")
    return reasons[:4]


def readiness_checklist(opportunity: dict[str, Any]) -> list[str]:
    checks = [
        "Confirm organization type and the full published eligibility requirements.",
        "Confirm UEI and SAM.gov registration status.",
        "Define the project scope, target population, and implementation partners.",
        "Estimate a budget and confirm required attachments.",
    ]
    if opportunity.get("cost_sharing_required") is True:
        checks.insert(2, "Confirm the ability to meet the stated cost-sharing requirement.")
    if opportunity.get("eligibility_description"):
        checks.insert(2, "Review the opportunity-specific eligibility narrative and geographic requirements.")
    return checks[:5]


class GrantRecommender:
    """TF-IDF corpus model and brute-force cosine nearest-neighbor retriever."""

    def __init__(self) -> None:
        self.vectorizer = TfidfVectorizer(**C.TFIDF_PARAMETERS)
        self.neighbors = NearestNeighbors(metric="cosine", algorithm="brute")
        self.opportunities: list[dict[str, Any]] = []
        self.matrix = None

    def fit(self, opportunities: list[dict[str, Any]]) -> "GrantRecommender":
        if not opportunities:
            raise ValueError("Cannot fit a grant recommender with zero opportunities.")
        self.opportunities = sorted(opportunities, key=lambda item: item["opportunity_id"])
        self.matrix = self.vectorizer.fit_transform([normalized_document(item) for item in self.opportunities])
        self.neighbors.fit(self.matrix)
        return self

    def recommend(self, profile: dict[str, Any], *, top_k: int = C.TOP_RECOMMENDATIONS, today: date | None = None) -> list[dict[str, Any]]:
        if self.matrix is None:
            raise ValueError("Fit the grant recommender before generating recommendations.")
        today = today or date.today()
        count = min(top_k, len(self.opportunities))
        query = self.vectorizer.transform([profile["profileText"]])
        distances, indices = self.neighbors.kneighbors(query, n_neighbors=count)
        matches = []
        for distance, index in zip(distances[0], indices[0]):
            opportunity = self.opportunities[int(index)]
            eligibility_status, eligibility_reason = screen_eligibility(opportunity, today=today)
            if eligibility_status == "Likely incompatible":
                continue
            category_score, evidence = _category_alignment(profile, opportunity)
            deadline_score, deadline_status, days_remaining = _deadline_score(opportunity, today)
            semantic_score = _clamp(1 - float(distance))
            match_score = _clamp(
                C.SCORE_WEIGHTS["semantic"] * semantic_score
                + C.SCORE_WEIGHTS["category"] * category_score
                + C.SCORE_WEIGHTS["eligibility"] * _eligibility_score(eligibility_status)
                + C.SCORE_WEIGHTS["deadline"] * deadline_score
            )
            matches.append({
                "opportunityId": opportunity["opportunity_id"],
                "matchScore": round(match_score, 4),
                "semanticScore": round(semantic_score, 4),
                "categoryScore": round(category_score, 4),
                "eligibilityScore": round(_eligibility_score(eligibility_status), 4),
                "deadlineScore": round(deadline_score, 4),
                "eligibilityStatus": eligibility_status,
                "eligibilityScreenReason": eligibility_reason,
                "deadlineStatus": deadline_status,
                "daysRemaining": days_remaining,
                "matchTier": _match_tier(match_score),
                "fitReasons": _fit_reasons(opportunity, evidence, deadline_status),
                "explanationEvidence": evidence,
                "readinessChecklist": readiness_checklist(opportunity),
            })
        return sorted(matches, key=lambda item: (-item["matchScore"], item["opportunityId"]))

    def artifact_metadata(self, *, source_retrieved_at: str) -> dict[str, Any]:
        if self.matrix is None:
            raise ValueError("Fit the grant recommender before reading metadata.")
        return {
            "modelVersion": C.MODEL_VERSION,
            "corpusSize": len(self.opportunities),
            "featureCount": int(self.matrix.shape[1]),
            "tfidfParameters": C.TFIDF_PARAMETERS,
            "nearestNeighbors": {"metric": "cosine", "algorithm": "brute"},
            "opportunityIds": [item["opportunity_id"] for item in self.opportunities],
            "sourceRetrievedAt": source_retrieved_at,
        }

    def save(self, directory: Path, *, source_retrieved_at: str) -> dict[str, Any]:
        """Persist the fitted vectorizer, neighbor index, IDs, and transparent metadata."""
        directory.mkdir(parents=True, exist_ok=True)
        payload = {"vectorizer": self.vectorizer, "neighbors": self.neighbors, "opportunity_ids": [item["opportunity_id"] for item in self.opportunities]}
        joblib.dump(payload, directory / "model.joblib")
        metadata = self.artifact_metadata(source_retrieved_at=source_retrieved_at)
        (directory / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        return metadata


def evaluation_metrics(
    opportunities: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    matches_by_county: dict[str, list[dict[str, Any]]],
    *,
    today: date,
) -> dict[str, Any]:
    all_matches = [match for matches in matches_by_county.values() for match in matches]
    agency_lookup = {item["opportunity_id"]: item.get("agency_code") or "Unknown" for item in candidates}
    category_lookup = {item["opportunity_id"]: item.get("funding_categories") or [] for item in candidates}
    total = len(opportunities) or 1
    return {
        "validOpportunityRate": sum(bool(item.get("opportunity_id") and item.get("title")) for item in opportunities) / total,
        "openDeadlineRate": sum(is_open_or_forecasted(item, today=today) for item in opportunities) / total,
        "healthcareRelevanceFilteringRate": len(candidates) / total,
        "opportunityCoverage": len({match["opportunityId"] for match in all_matches}) / max(len(candidates), 1),
        "countyRecommendationCoverage": sum(bool(matches) for matches in matches_by_county.values()) / max(len(matches_by_county), 1),
        "duplicateRecommendationRate": 1 - len({(county, match["opportunityId"]) for county, matches in matches_by_county.items() for match in matches}) / max(len(all_matches), 1),
        "recommendationAgencyDiversity": len({agency_lookup.get(match["opportunityId"]) for match in all_matches}),
        "recommendationCategoryDiversity": len({category for match in all_matches for category in category_lookup.get(match["opportunityId"], [])}),
        "nonemptyExplanationRate": sum(bool(match.get("fitReasons")) for match in all_matches) / max(len(all_matches), 1),
        "officialLinkValidityRate": sum(item.get("official_url", "").startswith("https://www.grants.gov/") for item in candidates) / max(len(candidates), 1),
    }
