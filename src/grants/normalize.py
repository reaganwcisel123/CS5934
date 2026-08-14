"""Canonical schema, cleaning, validation, and quality statistics for grants."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Any, Iterable

from src.grants import config as C

CANONICAL_FIELDS = (
    "opportunity_id", "opportunity_number", "title", "agency_code", "agency_name",
    "synopsis", "description", "applicant_types", "eligibility_description",
    "funding_categories", "funding_instruments", "assistance_listing_numbers",
    "posting_date", "opening_date", "closing_date", "archive_date", "award_floor",
    "award_ceiling", "estimated_total_funding", "expected_award_count",
    "cost_sharing_required", "status", "official_url", "retrieved_at", "source_year",
)


class _TextCleaner(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"p", "br", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean_text(value: Any) -> str:
    """Remove markup without flattening useful paragraph boundaries."""
    if value is None:
        return ""
    parser = _TextCleaner()
    parser.feed(str(value))
    text = unescape("".join(parser.parts)).replace("\xa0", " ")
    paragraphs = [re.sub(r"[ \t\r\f\v]+", " ", part).strip() for part in text.split("\n")]
    return "\n".join(part for part in paragraphs if part)


def parse_date(value: Any) -> str | None:
    """Safely normalize Grants.gov date strings to ISO dates."""
    if value in (None, ""):
        return None
    text = str(value).strip()
    for suffix in (" EDT", " EST", " UTC"):
        text = text.replace(suffix, "")
    for pattern in ("%m/%d/%Y", "%Y-%m-%d", "%b %d, %Y %I:%M:%S %p", "%B %d, %Y %I:%M:%S %p", "%Y-%m-%d-%H-%M-%S"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def parse_number(value: Any) -> int | float | None:
    """Parse publisher numeric/currency fields while preserving missing values."""
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(",", "").replace("$", "")
    if not text or text.lower() in {"n/a", "na", "not provided"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    try:
        value = float(text)
    except ValueError:
        return None
    value = -value if negative else value
    return int(value) if value.is_integer() else value


def parse_award_number(value: Any) -> int | float | None:
    """Treat publisher placeholder zero award values as unavailable, not $0 awards."""
    parsed = parse_number(value)
    return None if parsed == 0 else parsed


def _items(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    values = value if isinstance(value, list) else re.split(r"[|;,]", str(value))
    result: list[str] = []
    for item in values:
        if isinstance(item, dict):
            item = item.get("description") or item.get("name") or item.get("alnNumber") or item.get("id")
        cleaned = clean_text(item)
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def normalized_document(opportunity: dict[str, Any]) -> str:
    """The selected, auditable text fields used by the content model."""
    fields = (
        opportunity.get("title"), opportunity.get("agency_name"), opportunity.get("synopsis"),
        opportunity.get("description"), " ".join(opportunity.get("funding_categories") or []),
        " ".join(opportunity.get("funding_instruments") or []),
        " ".join(opportunity.get("applicant_types") or []), opportunity.get("eligibility_description"),
    )
    return "\n".join(clean_text(field) for field in fields if field)


def normalize_opportunity(raw: dict[str, Any], *, retrieved_at: str) -> dict[str, Any]:
    """Normalize one `{search_hit, detail}` response pair into the canonical schema."""
    search = raw.get("search_hit") or raw.get("search") or {}
    detail = raw.get("detail") or raw
    synopsis = detail.get("synopsis") or {}
    forecast = detail.get("forecast") or {}
    body = synopsis or forecast
    opportunity_id = str(_first(detail, "id", "opportunityId") or _first(search, "id") or "").strip()
    title = clean_text(_first(detail, "opportunityTitle", "title") or _first(search, "title"))
    agency_code = str(_first(detail, "owningAgencyCode", "agencyCode") or _first(body, "agencyCode") or _first(search, "agencyCode") or "").strip()
    alns = detail.get("alns") or detail.get("assistanceListings") or _first(search, "cfdaList", "alnist") or []
    status = str(_first(search, "oppStatus", "status") or _first(detail, "oppStatus", "status") or "unknown").lower()
    closing = parse_date(_first(body, "responseDate", "estApplicationResponseDate", "closingDate", "closeDate") or _first(search, "closeDate"))
    posting = parse_date(_first(body, "postingDate", "estSynopsisPostingDate") or _first(search, "openDate"))
    record = {
        "opportunity_id": opportunity_id,
        "opportunity_number": clean_text(_first(detail, "opportunityNumber", "number") or _first(search, "number")),
        "title": title,
        "agency_code": agency_code,
        "agency_name": clean_text(_first(search, "agency", "agencyName") or _first(body, "agencyName")),
        "synopsis": clean_text(_first(body, "synopsisDesc", "forecastDesc")),
        "description": clean_text(_first(body, "synopsisDesc", "forecastDesc", "description")),
        "applicant_types": _items(body.get("applicantTypes") or detail.get("applicantTypes")),
        "eligibility_description": clean_text(_first(body, "applicantEligibilityDesc", "eligibilityDescription")),
        "funding_categories": _items(body.get("fundingActivityCategories") or detail.get("fundingActivityCategories")),
        "funding_instruments": _items(body.get("fundingInstruments") or detail.get("fundingInstruments")),
        "assistance_listing_numbers": _items(alns),
        "posting_date": posting,
        "opening_date": parse_date(_first(search, "openDate") or _first(body, "postingDate")),
        "closing_date": closing,
        "archive_date": parse_date(_first(body, "archiveDate")),
        "award_floor": parse_award_number(_first(body, "awardFloor")),
        "award_ceiling": parse_award_number(_first(body, "awardCeiling")),
        "estimated_total_funding": parse_award_number(_first(body, "estimatedFunding")),
        "expected_award_count": parse_number(_first(body, "numberOfAwards")),
        "cost_sharing_required": _first(body, "costSharing"),
        "status": status,
        "official_url": C.OFFICIAL_RECORD_URL.format(opportunity_id=opportunity_id),
        "retrieved_at": retrieved_at,
        "source_year": int((posting or retrieved_at)[:4]),
    }
    validate_opportunity(record)
    return record


def validate_opportunity(opportunity: dict[str, Any]) -> None:
    missing = [field for field in ("opportunity_id", "title", "official_url") if not opportunity.get(field)]
    if missing:
        raise ValueError(f"Opportunity is missing required fields: {', '.join(missing)}")
    unknown = set(opportunity) - set(CANONICAL_FIELDS)
    if unknown:
        raise ValueError(f"Opportunity has unknown canonical fields: {sorted(unknown)}")


def is_open_or_forecasted(opportunity: dict[str, Any], *, today: date | None = None) -> bool:
    """Return whether a posted opportunity is still accepting applications."""
    if opportunity.get("status") not in C.ALLOWED_STATUSES:
        return False
    closing = opportunity.get("closing_date")
    if not closing:
        return True
    today = today or date.today()
    try:
        return date.fromisoformat(closing) >= today
    except ValueError:
        return False


def is_within_lookback(opportunity: dict[str, Any], *, today: date, days: int) -> bool:
    """Use canonical detailed posting dates with an inclusive UTC-day boundary."""
    if days not in C.GRANT_LOOKBACK_OPTIONS:
        raise ValueError(f"Unsupported grant lookback: {days}")
    posting = opportunity.get("posting_date")
    if not posting:
        return False
    try:
        return date.fromisoformat(posting) >= today - timedelta(days=days)
    except ValueError:
        return False


def normalize_many(raw_records: Iterable[dict[str, Any]], *, retrieved_at: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Normalize, validate, deduplicate, and summarize a raw opportunity batch."""
    raw_records = list(raw_records)
    unique: dict[str, dict[str, Any]] = {}
    duplicates = 0
    rejected = 0
    for raw in raw_records:
        try:
            opportunity = normalize_opportunity(raw, retrieved_at=retrieved_at)
        except ValueError:
            rejected += 1
            continue
        if opportunity["opportunity_id"] in unique:
            duplicates += 1
            continue
        unique[opportunity["opportunity_id"]] = opportunity
    opportunities = list(unique.values())
    counts = Counter(opportunity["status"] for opportunity in opportunities)
    agency_counts = Counter(opportunity["agency_code"] or "Unknown" for opportunity in opportunities)
    category_counts = Counter(category for opportunity in opportunities for category in opportunity["funding_categories"])
    missing = lambda field: sum(not opportunity.get(field) for opportunity in opportunities)
    metrics = {
        "raw_result_count": len(raw_records), "normalized_record_count": len(opportunities),
        "duplicate_count": duplicates, "rejected_count": rejected,
        "open_opportunity_count": counts["posted"], "forecasted_opportunity_count": counts["forecasted"],
        "expired_opportunity_count": sum(not is_open_or_forecasted(opportunity) for opportunity in opportunities),
        "missing_description_rate": missing("description") / len(opportunities) if opportunities else 0.0,
        "missing_eligibility_rate": missing("eligibility_description") / len(opportunities) if opportunities else 0.0,
        "missing_closing_date_rate": missing("closing_date") / len(opportunities) if opportunities else 0.0,
        "missing_award_range_rate": sum(not opportunity.get("award_floor") and not opportunity.get("award_ceiling") for opportunity in opportunities) / len(opportunities) if opportunities else 0.0,
        "agency_distribution": dict(sorted(agency_counts.items())),
        "category_distribution": dict(sorted(category_counts.items())),
    }
    return opportunities, metrics


def write_normalized_cache(
    opportunities: list[dict[str, Any]],
    metrics: dict[str, Any],
    *,
    retrieved_at: str,
    path: Path = C.NORMALIZED_CACHE_PATH,
) -> None:
    """Persist processed records separately from the raw API-response cache."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "retrieved_at": retrieved_at,
        "source": "Grants.gov",
        "records": opportunities,
        "quality": metrics,
    }, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
