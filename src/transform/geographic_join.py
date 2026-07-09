"""Geographic join utilities for attaching community SDoH to patient records.

The production join key for US-012 is ``county_fips``: a 5-digit county FIPS
code.  The functions here are intentionally pure so the join behavior can be
unit-tested without touching ingestion, the database, or the dashboard.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

GEO_KEY_COUNTY_FIPS = "county_fips"
UNMATCHED_RULE_RETAIN_WITH_NULL_CONTEXT = "retain_unmatched_with_null_context"
RURALITY_METHOD_POPULATION_PROXY = "county_population_inverse_share_proxy"
SDOH_DOMAINS = ("economic", "education", "food", "environment", "access")

# Placeholder features from the clinic-needs survey that can be populated once
# actual survey responses are available. Keep these nullable instead of guessing.
SURVEY_FEATURE_SCAFFOLD: dict[str, Any] = {
    "status": "pending_survey_results",
    "access_barriers": None,
    "community_health_issues": None,
    "common_social_needs": None,
    "social_needs_referral_barriers": None,
}


@dataclass(frozen=True)
class JoinCoverage:
    """Summary of how many patient records received community context."""

    total_records: int
    matched_records: int
    unmatched_records: int
    percent_matched: float
    geo_key: str = GEO_KEY_COUNTY_FIPS
    unmatched_rule: str = UNMATCHED_RULE_RETAIN_WITH_NULL_CONTEXT
    unmatched_keys: tuple[str | None, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_records": self.total_records,
            "matched_records": self.matched_records,
            "unmatched_records": self.unmatched_records,
            "percent_matched": self.percent_matched,
            "geo_key": self.geo_key,
            "unmatched_rule": self.unmatched_rule,
            "unmatched_keys": list(self.unmatched_keys),
        }


def normalize_county_fips(value: Any) -> str | None:
    """Normalize a county FIPS value to a 5-character string.

    Examples: ``51001`` -> ``"51001"`` and ``"1"`` -> ``"00001"``.
    Missing or blank values return ``None`` so they are treated as unmatched.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text.zfill(5) if text.isdigit() else text


def join_sdoh_to_patients(
    patients: Iterable[Mapping[str, Any]],
    sdoh_by_geo: Mapping[str, Mapping[str, Any]],
    *,
    geo_key: str = GEO_KEY_COUNTY_FIPS,
    survey_scaffold: Mapping[str, Any] | None = None,
    unmatched_rule: str = UNMATCHED_RULE_RETAIN_WITH_NULL_CONTEXT,
) -> tuple[list[dict[str, Any]], JoinCoverage]:
    """Join community-level SDoH context onto patient dictionaries.

    Unmatched patient records are retained and marked with null SDoH/rurality
    context. This keeps row counts stable for downstream analysis while making
    coverage loss explicit through both record-level status and the returned
    ``JoinCoverage`` summary.
    """
    if unmatched_rule != UNMATCHED_RULE_RETAIN_WITH_NULL_CONTEXT:
        raise ValueError(f"Unsupported unmatched_rule: {unmatched_rule}")

    normalized_context = {
        normalize_county_fips(key): deepcopy(value)
        for key, value in sdoh_by_geo.items()
        if normalize_county_fips(key) is not None
    }

    base_survey = dict(SURVEY_FEATURE_SCAFFOLD if survey_scaffold is None else survey_scaffold)
    joined: list[dict[str, Any]] = []
    matched = 0
    unmatched_keys: list[str | None] = []

    for patient in patients:
        row = deepcopy(dict(patient))
        key = normalize_county_fips(row.get(geo_key))
        context = normalized_context.get(key)

        row["sdohJoinKey"] = geo_key
        row["sdohGeoKey"] = key

        if context is None:
            row["sdohJoinStatus"] = "unmatched"
            row["nb"] = {domain: None for domain in SDOH_DOMAINS}
            row["rural"] = None
            row["ruralityMethod"] = RURALITY_METHOD_POPULATION_PROXY
            row["needIndex"] = None
            row["surveyFeatures"] = deepcopy(base_survey)
            unmatched_keys.append(key)
        else:
            matched += 1
            row["sdohJoinStatus"] = "matched"
            row["nb"] = _neighborhood_burdens(context)
            row["rural"] = context.get("rural", context.get("rurality"))
            row["ruralityMethod"] = context.get("ruralityMethod", RURALITY_METHOD_POPULATION_PROXY)
            row["needIndex"] = context.get("needIndex")
            row["surveyFeatures"] = _survey_features(base_survey, context)

        joined.append(row)

    total = len(joined)
    unmatched = total - matched
    coverage = JoinCoverage(
        total_records=total,
        matched_records=matched,
        unmatched_records=unmatched,
        percent_matched=round((matched / total) * 100, 1) if total else 100.0,
        geo_key=geo_key,
        unmatched_rule=unmatched_rule,
        unmatched_keys=tuple(sorted(set(unmatched_keys), key=lambda x: "" if x is None else x)),
    )
    return joined, coverage


def summarize_join_coverages(coverages: Iterable[JoinCoverage]) -> JoinCoverage:
    """Combine multiple county-level coverage objects into one build summary."""
    coverage_list = list(coverages)
    total = sum(c.total_records for c in coverage_list)
    matched = sum(c.matched_records for c in coverage_list)
    unmatched = total - matched
    keys: set[str | None] = set()
    for coverage in coverage_list:
        keys.update(coverage.unmatched_keys)
    geo_key = coverage_list[0].geo_key if coverage_list else GEO_KEY_COUNTY_FIPS
    unmatched_rule = (coverage_list[0].unmatched_rule
                      if coverage_list else UNMATCHED_RULE_RETAIN_WITH_NULL_CONTEXT)
    return JoinCoverage(
        total_records=total,
        matched_records=matched,
        unmatched_records=unmatched,
        percent_matched=round((matched / total) * 100, 1) if total else 100.0,
        geo_key=geo_key,
        unmatched_rule=unmatched_rule,
        unmatched_keys=tuple(sorted(keys, key=lambda x: "" if x is None else x)),
    )


def _neighborhood_burdens(context: Mapping[str, Any]) -> dict[str, Any]:
    raw = context.get("nb", context.get("dom", {})) or {}
    return {domain: raw.get(domain) for domain in SDOH_DOMAINS}


def _survey_features(base_survey: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    features = deepcopy(dict(base_survey))
    context_features = context.get("surveyFeatures", context.get("survey_features", {})) or {}
    features.update(context_features)
    return features