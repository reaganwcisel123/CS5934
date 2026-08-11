"""Deterministic county-informed clinic planning profiles from Atlas fields."""

from __future__ import annotations

from typing import Any

from src.grants import config as C


def _value(record: dict[str, Any], dotted_field: str) -> float | None:
    current: Any = record
    for part in dotted_field.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    try:
        return float(current) if current is not None else None
    except (TypeError, ValueError):
        return None


def _activate(record: dict[str, Any], *, tag: str, label: str, field: str, threshold: float, explanation: str) -> dict[str, Any] | None:
    value = _value(record, field)
    if value is None or value < threshold:
        return None
    return {
        "tag": tag,
        "label": label,
        "sourceField": field,
        "fieldValue": round(value, 1),
        "thresholdRule": f"{field} >= {threshold}",
        "explanation": explanation,
    }


def build_profile(record: dict[str, Any]) -> dict[str, Any]:
    """Create a controlled, non-clinical planning profile for one locality."""
    thresholds = C.PROFILE_THRESHOLDS
    activated = [
        _activate(record, tag="rural_healthcare_delivery", label="rural healthcare delivery", field="rural", threshold=thresholds["rural"], explanation="The Atlas classifies this locality as more rural on its normalized rurality field."),
        _activate(record, tag="primary_care_workforce_shortage", label="primary care workforce shortage", field="hpsaScore", threshold=thresholds["hpsa_score"], explanation="The primary-care HPSA score meets the planning threshold for a workforce-shortage context."),
        _activate(record, tag="behavioral_health_access", label="behavioral health access", field="outcomes.mhlth", threshold=thresholds["mental_distress"], explanation="The local mental-distress measure meets the planning threshold."),
        _activate(record, tag="mental_health_services", label="mental health services", field="outcomes.mhlth", threshold=thresholds["mental_distress"] + 3, explanation="The local mental-distress measure is above the elevated-services threshold."),
        _activate(record, tag="diabetes_prevention_and_management", label="diabetes prevention and management", field="outcomes.diabetes", threshold=thresholds["diabetes"], explanation="The local diabetes prevalence meets the planning threshold."),
        _activate(record, tag="hypertension_management", label="hypertension management", field="outcomes.bphigh", threshold=thresholds["hypertension"], explanation="The local high-blood-pressure prevalence meets the planning threshold."),
        _activate(record, tag="obesity_prevention", label="obesity prevention", field="outcomes.obesity", threshold=thresholds["obesity"], explanation="The local obesity prevalence meets the planning threshold."),
        _activate(record, tag="food_access", label="food access", field="dom.food", threshold=thresholds["food_burden"], explanation="The Atlas food-access burden meets the planning threshold."),
        _activate(record, tag="care_coordination", label="care coordination", field="dom.access", threshold=thresholds["access_burden"], explanation="The Atlas care-access burden meets the planning threshold."),
        _activate(record, tag="community_outreach", label="community outreach", field="dom.economic", threshold=thresholds["economic_burden"], explanation="The Atlas economic-burden domain meets the planning threshold for outreach context."),
        _activate(record, tag="health_equity", label="health equity", field="needIndex", threshold=thresholds["need_index"], explanation="The composite Atlas need index meets the planning threshold for equity-focused planning."),
        _activate(record, tag="clinic_infrastructure", label="clinic infrastructure", field="dom.environment", threshold=thresholds["environment_burden"], explanation="The environmental-burden domain meets the planning threshold for infrastructure context."),
        _activate(record, tag="quality_improvement", label="quality improvement", field="needIndex", threshold=thresholds["need_index"], explanation="The composite Atlas need index meets the planning threshold for quality-improvement planning."),
    ]
    tags = [item for item in activated if item]
    priority_labels = [item["label"] for item in tags]
    locality = record.get("name") or "Virginia locality"
    region = record.get("region") or "Virginia"
    profile_text = (
        f"County-informed clinic planning profile for {locality}, {region}, Virginia. "
        f"Priority planning tags: {', '.join(priority_labels) if priority_labels else 'rural healthcare planning context'}. "
        "This profile is derived from public county indicators and is not a confirmed clinic strategy."
    )
    return {
        "countyFips": str(record.get("id") or ""),
        "countyName": locality,
        "region": region,
        "rurality": record.get("rural"),
        "needIndex": record.get("needIndex"),
        "hpsaScore": record.get("hpsaScore"),
        "profileTags": tags,
        "profileText": profile_text,
    }


def build_profiles(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Create profiles for every Atlas locality with a stable county FIPS ID."""
    return {str(record["id"]): build_profile(record) for record in records if record.get("id")}
