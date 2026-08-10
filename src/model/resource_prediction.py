"""Predict clinic resource demand from county health indicators (Predictive Analytics epic).

A rules-based engine, not a trained model: there is no historical clinic
utilization time series anywhere in this project's data sources today, only a
cross-sectional county/patient snapshot, so a forecast built on a trend model
would be fabricating history it doesn't have. Instead this module multiplies
documented, config-driven assumptions (prevalence x visit rate, staffing
ratios, per-encounter supply factors) by the county's own indicators, the same
"disclosed factor x observed input" approach `supply_needs.py` already uses
for notifiable-disease stocking.

Every assumption lives in data/reference/resource_planning_config.yml, never
in this file, so "forecast assumptions configurable without code changes"
holds literally. Every input the engine reads is resolved through a
three-tier fallback (county value -> statewide mean -> config default), and
every prediction reports which tier each input actually used, so missing data
degrades the confidence level instead of silently becoming a false-precision
number.

`historical_monthly_volume` / `seasonal_index` are accepted but unused unless
a caller supplies them -- the seam a future ML model or a real EHR/utilization
feed plugs into without changing this function's contract.
"""

from __future__ import annotations

import csv
import io
import math

import yaml

from src.catalog import REPO_ROOT

CONFIG_PATH = REPO_ROOT / "data" / "reference" / "resource_planning_config.yml"

INSUFFICIENT_DATA = "insufficient_data"
OK = "ok"

DISCLAIMER = (
    "Planning aid only. Quantities are modelled estimates from county health "
    "indicators and published primary-care planning benchmarks, not a "
    "procurement instruction, a staffing mandate, or a clinical protocol."
)

# Every quantity below is sized off the county's total population (the same
# `patients` figure -- sourced from Census county estimates -- that the
# NNDSS county forecast already allocates against). That is a county-wide
# capacity estimate, the same population basis HRSA uses to compute a HPSA
# shortage score, not one specific clinic's roster. Carried on every
# prediction so a single small clinic doesn't read "25 physicians" as its
# own staffing target.
SCOPE_NOTE = (
    "These figures estimate total demand across the county's primary-care "
    "capacity as a whole (population basis: county patient population), not "
    "one specific clinic's roster. Scale every quantity by your clinic's "
    "estimated share of the county's patient panel to size your own plan."
)

CONDITION_LABELS = {
    "hypertension": "Hypertension",
    "diabetes": "Diabetes",
    "behavioral_health": "Behavioral health",
    "weight_related": "Weight-related conditions",
    "asthma": "Asthma",
    "hyperlipidemia": "Hyperlipidemia (cholesterol)",
    "acute_care": "Acute / walk-in care",
}


def load_config(path=None) -> dict:
    p = path or CONFIG_PATH
    if not p.exists():
        raise FileNotFoundError(f"Missing resource planning config: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def review_status(config: dict | None = None) -> dict:
    """Whether the assumptions in the config have been signed off by a clinician."""
    cfg = config if config is not None else load_config()
    return {
        "clinical_review": cfg.get("clinical_review", "pending"),
        "note": (cfg.get("clinical_review_note") or "").strip(),
    }


def state_summary(records: list[dict], fields: list[str] | None = None,
                   config: dict | None = None) -> dict[str, float | None]:
    """Statewide mean of every field the engine may fall back to."""
    cfg = config if config is not None else load_config()
    field_list = fields if fields is not None else cfg["confidence"]["fields_checked"]
    out: dict[str, float | None] = {}
    for field in field_list:
        values = [float(v) for r in records if (v := _get_path(r, field)) is not None]
        out[field] = (sum(values) / len(values)) if values else None
    return out


def predict_resources(
    county: dict,
    window_days: int,
    config: dict | None = None,
    state_summary: dict | None = None,
    overrides: dict | None = None,
    historical_monthly_volume: float | None = None,
    seasonal_index: float | None = None,
) -> dict:
    """Predict medication, supply, equipment, and staffing needs for one county.

    `overrides` maps "category.item.factor_name" (e.g.
    "medications.hypertension_medications.fills_per_encounter") to a
    replacement value, so a clinic can correct a single assumption without
    editing the shared config file.
    """
    cfg = config if config is not None else load_config()
    ss = state_summary or {}
    overrides = overrides or {}
    fips, name = county.get("id"), county.get("name")
    patients = county.get("patients")

    if not patients or patients <= 0:
        return _insufficient_data(fips, name, window_days, cfg)
    patients = float(patients)

    fb = cfg["fallback_defaults"]
    access, access_tier = _resolve(county, "dom.access", ss, fb.get("access_burden"))
    uninsured, uninsured_tier = _resolve(county, "sdoh.uninsured_rate", ss, fb.get("uninsured_rate_pct"))
    age65, age65_tier = _resolve(county, "sdoh.age65_pct", ss, fb.get("age65_pct"))
    child_immun, child_immun_tier = _resolve(county, "measures.child_immun", ss, fb.get("child_immun_pct"))
    need_index, need_index_tier = _resolve(county, "needIndex", ss, fb.get("need_index"))
    hpsa_score, hpsa_tier = _resolve(county, "hpsaScore", ss, fb.get("hpsa_score"))

    util = cfg["utilization"]
    access_uplift = min(util["rural_access_uplift_max"], (access or 0.0) * util["rural_access_uplift_per_point"])
    uninsured_damp = min(util["uninsured_dampening_max"], (uninsured or 0.0) * util["uninsured_dampening_per_point"])
    effective_rate = util["base_encounters_per_patient_per_30d"] * (1 + access_uplift) * (1 - uninsured_damp)

    historical_used = historical_monthly_volume is not None
    base_monthly = float(historical_monthly_volume) if historical_used else patients * effective_rate
    seasonal_mult = float(seasonal_index) if seasonal_index is not None else 1.0
    estimated_patient_volume = _ceil(base_monthly * (window_days / 30.0) * seasonal_mult)

    conditions_out = _condition_encounters(county, cfg, ss, window_days, overrides, patients)
    medications = _medications(cfg, conditions_out, child_immun, patients, window_days, overrides)
    medical_supplies = _medical_supplies(cfg, conditions_out, estimated_patient_volume, overrides)
    diagnostic_equipment = _diagnostic_equipment(cfg, conditions_out, patients, estimated_patient_volume, overrides)
    staffing = _staffing(cfg, conditions_out, patients, access, need_index, overrides)

    field_tiers = {spec["outcome_field"]: conditions_out[key]["prevalence_tier"]
                   for key, spec in cfg["conditions"].items() if spec.get("outcome_field")}
    field_tiers.update({
        "sdoh.uninsured_rate": uninsured_tier, "sdoh.age65_pct": age65_tier,
        "measures.child_immun": child_immun_tier, "dom.access": access_tier,
        "hpsaScore": hpsa_tier, "needIndex": need_index_tier, "patients": "county",
    })

    fields_checked = cfg["confidence"]["fields_checked"]
    missing = [f for f in fields_checked if field_tiers.get(f, "default") != "county"]
    confidence_level = _confidence_level(cfg, len(missing))

    priority_score, priority_level, priority_factors = _priority(
        cfg, need_index, hpsa_score, uninsured, len(missing), len(fields_checked))

    explanation = _explain(
        window_days, patients, estimated_patient_volume, conditions_out,
        access, access_uplift, uninsured, uninsured_damp, missing,
        priority_level, priority_score, confidence_level, len(fields_checked))

    return {
        "county_fips": fips,
        "county_name": name,
        "planning_window_days": window_days,
        "status": OK,
        "estimated_patient_volume": estimated_patient_volume,
        "expected_encounters_by_condition": conditions_out,
        "medications": medications,
        "medical_supplies": medical_supplies,
        "diagnostic_equipment": diagnostic_equipment,
        "staffing": staffing,
        "priority_level": priority_level,
        "priority_score": priority_score,
        "priority_factors": priority_factors,
        "confidence_level": confidence_level,
        "confidence_detail": {
            "fields_checked": len(fields_checked),
            "fields_from_county_data": len(fields_checked) - len(missing),
            "fields_from_fallback": len(missing),
            "fallback_fields": sorted(missing),
        },
        "explanation": explanation,
        "assumptions_version": cfg.get("version"),
        "fallbacks_used": dict(sorted(field_tiers.items())),
        "historical_data_used": historical_used,
        "clinical_review": review_status(cfg),
        "disclaimer": DISCLAIMER,
        "scope_note": SCOPE_NOTE,
    }


def to_csv_rows(prediction: dict) -> list[dict]:
    """Flatten every recommended item into export-ready rows."""
    meta = {
        "county_fips": prediction.get("county_fips"),
        "county_name": prediction.get("county_name"),
        "planning_window_days": prediction.get("planning_window_days"),
        "priority_level": prediction.get("priority_level"),
        "confidence_level": prediction.get("confidence_level"),
    }
    rows = []
    for category in ("medications", "medical_supplies", "diagnostic_equipment", "staffing"):
        for key, item in (prediction.get(category) or {}).items():
            rows.append({
                **meta,
                "category": category,
                "item": key,
                "quantity": item.get("quantity"),
                "unit": item.get("unit"),
                "driver": item.get("driver") or "",
                "overridden": item.get("overridden", False),
            })
    return rows


def to_export_csv(prediction: dict) -> str:
    rows = to_csv_rows(prediction)
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


# --- internals ----------------------------------------------------------------

def _get_path(record: dict, path: str):
    node = record
    for part in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def _resolve(record: dict, path: str, ss: dict, default) -> tuple[float | None, str]:
    v = _get_path(record, path)
    if v is not None:
        return float(v), "county"
    sv = ss.get(path)
    if sv is not None:
        return float(sv), "state"
    return (float(default) if default is not None else None), "default"


def _ceil(x: float) -> int:
    """Round up: under-planning a clinic is worse than over-planning it."""
    return int(math.ceil(max(0.0, x)))


def _override(overrides: dict, key: str, fallback):
    return (float(overrides[key]), True) if key in overrides else (fallback, False)


def _insufficient_data(fips, name, window_days, cfg) -> dict:
    return {
        "county_fips": fips, "county_name": name, "planning_window_days": window_days,
        "status": INSUFFICIENT_DATA,
        "estimated_patient_volume": None, "expected_encounters_by_condition": {},
        "medications": {}, "medical_supplies": {}, "diagnostic_equipment": {}, "staffing": {},
        "priority_level": None, "priority_score": None, "priority_factors": [],
        "confidence_level": None,
        "confidence_detail": {"fields_checked": 0, "fields_from_county_data": 0,
                               "fields_from_fallback": 0, "fallback_fields": []},
        "explanation": ["No population figure is available for this county; a plan cannot be sized."],
        "assumptions_version": cfg.get("version"), "fallbacks_used": {},
        "historical_data_used": False, "clinical_review": review_status(cfg),
        "disclaimer": DISCLAIMER, "scope_note": SCOPE_NOTE,
    }


def _condition_encounters(county, cfg, ss, window_days, overrides, patients) -> dict:
    out = {}
    for key, spec in cfg["conditions"].items():
        outcome_field = spec.get("outcome_field")
        annual_cases = None
        if outcome_field:
            prevalence, tier = _resolve(county, outcome_field, ss, spec.get("default_prevalence_pct"))
            prevalence, overridden = _override(overrides, f"conditions.{key}.prevalence_pct", prevalence)
            if overridden:
                tier = "override"
            visits = spec.get("annual_visits_per_case") or 0.0
            annual_cases = patients * ((prevalence or 0.0) / 100.0)
            annual_encounters = annual_cases * visits
        else:
            prevalence, tier = None, "default"
            epy, overridden = _override(
                overrides, f"conditions.{key}.encounters_per_patient_per_year",
                spec.get("encounters_per_patient_per_year") or 0.0)
            if overridden:
                tier = "override"
            annual_encounters = patients * epy

        window_encounters = annual_encounters * (window_days / 365.0)
        window_cases = annual_cases * (window_days / 365.0) if annual_cases is not None else None

        out[key] = {
            "condition": key,
            "label": CONDITION_LABELS.get(key, key),
            "prevalence_pct": round(prevalence, 2) if prevalence is not None else None,
            "prevalence_tier": tier,
            "annual_visits_per_case": spec.get("annual_visits_per_case"),
            "annual_cases": round(annual_cases, 2) if annual_cases is not None else None,
            "window_cases": round(window_cases, 2) if window_cases is not None else None,
            "expected_encounters": _ceil(window_encounters),
        }
    return out


def _medications(cfg, conditions_out, child_immun, patients, window_days, overrides) -> dict:
    out = {}
    for key, spec in cfg["medications"].items():
        unit = spec.get("unit")
        if spec.get("driver") == "immunization_gap":
            gap_pct = max(0.0, 100.0 - (child_immun or 0.0))
            factor, overridden = _override(
                overrides, f"medications.{key}.doses_per_percent_gap_per_patient",
                spec["doses_per_percent_gap_per_patient"])
            annual = patients * gap_pct * factor
            qty = _ceil(annual * (window_days / 365.0))
            out[key] = {"item": key, "unit": unit, "quantity": qty, "driver": "immunization_gap",
                        "immunization_gap_pct": round(gap_pct, 1), "factor": factor,
                        "overridden": overridden}
        else:
            cond = spec["condition"]
            encounters = conditions_out[cond]["expected_encounters"]
            factor, overridden = _override(
                overrides, f"medications.{key}.fills_per_encounter", spec["fills_per_encounter"])
            qty = _ceil(encounters * factor)
            out[key] = {"item": key, "unit": unit, "quantity": qty, "driver": cond,
                        "driven_by_encounters": encounters, "factor": factor,
                        "overridden": overridden}
    return out


def _medical_supplies(cfg, conditions_out, total_window_encounters, overrides) -> dict:
    out = {}
    for key, spec in cfg["medical_supplies"].items():
        unit, basis = spec.get("unit"), spec["basis"]
        if basis == "condition":
            cond = spec["condition"]
            basis_qty = conditions_out[cond]["expected_encounters"]
            factor, overridden = _override(
                overrides, f"medical_supplies.{key}.per_case_encounter", spec["per_case_encounter"])
            driver = cond
        else:
            basis_qty = total_window_encounters
            factor, overridden = _override(
                overrides, f"medical_supplies.{key}.per_encounter", spec["per_encounter"])
            driver = "estimated_patient_volume"
        out[key] = {"item": key, "unit": unit, "quantity": _ceil(basis_qty * factor),
                    "basis": basis, "driver": driver, "factor": factor, "overridden": overridden}
    return out


def _diagnostic_equipment(cfg, conditions_out, patients, total_window_encounters, overrides) -> dict:
    out = {}
    for key, spec in cfg["diagnostic_equipment"].items():
        unit, basis = spec.get("unit"), spec["basis"]
        if basis == "panel":
            factor, overridden = _override(overrides, f"diagnostic_equipment.{key}.per_patients", spec["per_patients"])
            qty = _ceil(patients / factor) if factor else 0
            driver = "panel_size"
        elif basis == "condition_cases":
            cond = spec["condition"]
            cases = conditions_out[cond]["window_cases"] or 0.0
            factor, overridden = _override(overrides, f"diagnostic_equipment.{key}.per_cases", spec["per_cases"])
            qty = _ceil(cases / factor) if factor else 0
            driver = cond
        else:
            factor, overridden = _override(overrides, f"diagnostic_equipment.{key}.per_encounter", spec["per_encounter"])
            qty = _ceil(total_window_encounters * factor)
            driver = "estimated_patient_volume"
        out[key] = {"item": key, "unit": unit, "quantity": qty, "basis": basis, "driver": driver,
                    "factor": factor, "overridden": overridden, "note": spec.get("note")}
    return out


def _staffing(cfg, conditions_out, patients, access, need_index, overrides) -> dict:
    out = {}
    for key, spec in cfg["staffing"].items():
        if key == "behavioral_health_specialists":
            cond = spec["condition"]
            annual_cases = conditions_out[cond]["annual_cases"] or 0.0
            factor, overridden = _override(overrides, f"staffing.{key}.cases_per_fte", spec["cases_per_fte"])
            fte = (annual_cases / factor) if factor else 0.0
            out[key] = {"item": key, "unit": "FTE", "quantity": round(fte, 2), "driver": cond,
                        "factor": factor, "overridden": overridden}
            continue

        factor, overridden = _override(overrides, f"staffing.{key}.patients_per_fte", spec["patients_per_fte"])
        uplift = 0.0
        if "rural_uplift_max" in spec:
            uplift = min(spec["rural_uplift_max"], (access or 0.0) / 100.0 * spec["rural_uplift_max"])
            driver = "panel_size (rurality-adjusted)"
        elif "need_index_uplift_max" in spec:
            uplift = min(spec["need_index_uplift_max"], (need_index or 0.0) / 100.0 * spec["need_index_uplift_max"])
            driver = "panel_size (need-adjusted)"
        else:
            driver = "panel_size"
        effective = factor * (1 - uplift)
        fte = (patients / effective) if effective else 0.0
        out[key] = {"item": key, "unit": "FTE", "quantity": round(fte, 2), "driver": driver,
                    "factor": factor, "uplift_applied": round(uplift, 3), "overridden": overridden}
    return out


def _priority(cfg, need_index, hpsa_score, uninsured, missing_count, total_fields) -> tuple[float, str, list[str]]:
    w = cfg["priority"]["weights"]
    hpsa_component = min(100.0, (hpsa_score or 0.0) / 26.0 * 100.0)
    completeness_penalty = (missing_count / total_fields * 100.0) if total_fields else 0.0

    score = ((need_index or 0.0) * w["need_index"]
             + hpsa_component * w["hpsa_score"]
             + (uninsured or 0.0) * w["uninsured_rate"]
             + completeness_penalty * w["data_completeness_penalty"])
    score = round(min(100.0, max(0.0, score)), 1)

    th = cfg["priority"]["thresholds"]
    if score >= th["critical"]:
        level = "Critical"
    elif score >= th["high"]:
        level = "High"
    elif score >= th["medium"]:
        level = "Medium"
    else:
        level = "Low"

    factors = [
        f"Unmet-need index {need_index:.1f}/100 (weight {w['need_index']*100:.0f}%)",
        f"HPSA shortage score {hpsa_score:.0f}/26 (weight {w['hpsa_score']*100:.0f}%)",
        f"Uninsured rate {uninsured:.1f}% (weight {w['uninsured_rate']*100:.0f}%)",
        f"{missing_count} of {total_fields} inputs used a state or default fallback "
        f"(weight {w['data_completeness_penalty']*100:.0f}%)",
    ]
    return score, level, factors


def _confidence_level(cfg, missing_count: int) -> str:
    c = cfg["confidence"]
    if missing_count <= c["high_max_missing"]:
        return "High"
    if missing_count <= c["medium_max_missing"]:
        return "Medium"
    return "Low"


def _explain(window_days, patients, estimated_patient_volume, conditions_out, access,
             access_uplift, uninsured, uninsured_damp, missing, priority_level,
             priority_score, confidence_level, total_fields) -> list[str]:
    lines = [
        f"Estimated {estimated_patient_volume:,} patient encounters over the next "
        f"{window_days} days, from a panel of {int(patients):,} patients."
    ]

    ranked = sorted(conditions_out.values(), key=lambda v: v["expected_encounters"], reverse=True)
    top = next((c for c in ranked if c["prevalence_pct"] is not None), None)
    if top:
        lines.append(
            f"{top['label']} is the largest single driver: {top['prevalence_pct']}% "
            f"prevalence x {top['annual_visits_per_case']} visits/case/year."
        )

    if access_uplift > 0:
        lines.append(
            f"Care-access burden ({access:.0f}/100) added {access_uplift*100:.1f}% to expected utilization."
        )
    if uninsured_damp > 0:
        lines.append(
            f"Uninsured rate ({uninsured:.1f}%) reduced expected completed encounters by "
            f"{uninsured_damp*100:.1f}%."
        )
    if missing:
        lines.append(
            f"No county-observed value for {', '.join(sorted(missing))}; used the "
            f"statewide mean or the config default instead (see fallbacks_used)."
        )

    lines.append(f"Priority: {priority_level} ({priority_score}/100), driven mainly by the unmet-need index and HPSA shortage score.")
    lines.append(
        f"Confidence: {confidence_level} -- {len(missing)} of {total_fields} inputs relied on a fallback "
        f"rather than a county-observed value."
    )
    return lines
