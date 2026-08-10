"""Predictive Analytics epic: the rules-based resource-prediction engine."""

from __future__ import annotations

import json

import pytest

from src.catalog import REPO_ROOT
from src.model import resource_prediction as rp

CFG = {
    "version": 1,
    "planning_windows_days": [30, 60, 90],
    "clinical_review": "pending",
    "clinical_review_note": "note",
    "fallback_defaults": {
        "uninsured_rate_pct": 10.0, "age65_pct": 20.0, "child_immun_pct": 50.0,
        "access_burden": 40.0, "need_index": 50.0, "hpsa_score": 10.0,
    },
    "utilization": {
        "base_encounters_per_patient_per_30d": 0.2,
        "rural_access_uplift_per_point": 0.0, "rural_access_uplift_max": 0.0,
        "uninsured_dampening_per_point": 0.0, "uninsured_dampening_max": 0.0,
    },
    "conditions": {
        "diabetes": {"outcome_field": "outcomes.diabetes", "annual_visits_per_case": 4.0,
                     "default_prevalence_pct": 10.0},
        "acute_care": {"outcome_field": None, "annual_visits_per_case": None,
                       "encounters_per_patient_per_year": 1.0, "default_prevalence_pct": None},
    },
    "medications": {
        "diabetes_medications_and_insulin": {"condition": "diabetes", "fills_per_encounter": 1.0, "unit": "fill"},
        "vaccines": {"driver": "immunization_gap", "doses_per_percent_gap_per_patient": 0.01, "unit": "dose"},
    },
    "medical_supplies": {
        "gloves": {"basis": "encounter", "per_encounter": 1.0, "unit": "pair"},
        "test_strips": {"basis": "condition", "condition": "diabetes", "per_case_encounter": 2.0, "unit": "each"},
    },
    "diagnostic_equipment": {
        "glucose_monitors": {"basis": "condition_cases", "condition": "diabetes", "per_cases": 10, "unit": "monitor"},
        "cuffs": {"basis": "panel", "per_patients": 100, "unit": "cuff"},
        "poc_kits": {"basis": "encounter", "per_encounter": 1.0, "unit": "kit"},
    },
    "staffing": {
        "physicians": {"patients_per_fte": 1000},
        "behavioral_health_specialists": {"condition": "diabetes", "cases_per_fte": 100},
    },
    "priority": {
        "weights": {"need_index": 0.4, "hpsa_score": 0.3, "uninsured_rate": 0.2, "data_completeness_penalty": 0.1},
        "thresholds": {"critical": 75, "high": 55, "medium": 35},
    },
    "confidence": {
        "fields_checked": ["outcomes.diabetes", "sdoh.uninsured_rate", "needIndex", "hpsaScore", "patients"],
        "high_max_missing": 1, "medium_max_missing": 3,
    },
}


def _county(**overrides) -> dict:
    base = {
        "id": "51999", "name": "Test County", "patients": 1000,
        "outcomes": {"diabetes": 20.0}, "dom": {"access": 40.0},
        "sdoh": {"uninsured_rate": 10.0}, "measures": {"child_immun": 50.0},
        "needIndex": 50.0, "hpsaScore": 10.0,
    }
    base.update(overrides)
    return base


# --- core quantity math -------------------------------------------------------

def test_estimated_patient_volume_scales_off_the_panel_and_utilization_rate():
    out = rp.predict_resources(_county(), 30, config=CFG, state_summary={})

    # 1000 patients * 0.2 encounters/patient/30d * (30/30) = 200
    assert out["estimated_patient_volume"] == 200


def test_condition_encounters_multiply_prevalence_by_visit_rate():
    out = rp.predict_resources(_county(), 30, config=CFG, state_summary={})
    diabetes = out["expected_encounters_by_condition"]["diabetes"]

    # 1000 patients * 20% prevalence = 200 annual cases; * 4 visits/case/year
    # = 800 annual encounters; * 30/365 = 65.75 -> ceil 66.
    assert diabetes["prevalence_pct"] == 20.0
    assert diabetes["prevalence_tier"] == "county"
    assert diabetes["expected_encounters"] == 66


def test_medication_quantity_is_encounters_times_fills_per_encounter():
    out = rp.predict_resources(_county(), 30, config=CFG, state_summary={})

    assert out["medications"]["diabetes_medications_and_insulin"]["quantity"] == 66


def test_vaccine_quantity_is_driven_by_the_immunization_gap_not_a_condition():
    out = rp.predict_resources(_county(), 30, config=CFG, state_summary={})

    # gap = 100 - 50 = 50; 1000 patients * 50 * 0.01 = 500 annual; * 30/365 -> ceil 42.
    assert out["medications"]["vaccines"]["immunization_gap_pct"] == 50.0
    assert out["medications"]["vaccines"]["quantity"] == 42


def test_condition_basis_supply_uses_condition_encounters_not_total_volume():
    out = rp.predict_resources(_county(), 30, config=CFG, state_summary={})

    # 66 diabetes encounters * 2.0 test strips/encounter = 132.
    assert out["medical_supplies"]["test_strips"]["quantity"] == 132
    assert out["medical_supplies"]["test_strips"]["driver"] == "diabetes"


def test_encounter_basis_supply_uses_total_estimated_volume():
    out = rp.predict_resources(_county(), 30, config=CFG, state_summary={})

    assert out["medical_supplies"]["gloves"]["quantity"] == 200
    assert out["medical_supplies"]["gloves"]["driver"] == "estimated_patient_volume"


def test_panel_basis_equipment_divides_panel_by_the_ratio():
    out = rp.predict_resources(_county(), 30, config=CFG, state_summary={})

    assert out["diagnostic_equipment"]["cuffs"]["quantity"] == 10  # 1000 / 100


def test_condition_cases_basis_equipment_uses_window_cases_not_encounters():
    out = rp.predict_resources(_county(), 30, config=CFG, state_summary={})

    # window_cases = 200 * 30/365 = 16.4384 / 10 -> ceil 2.
    assert out["diagnostic_equipment"]["glucose_monitors"]["quantity"] == 2


def test_staffing_is_a_fractional_fte_not_rounded_up():
    out = rp.predict_resources(_county(), 30, config=CFG, state_summary={})

    # 1000 patients / 1000 patients-per-fte = 1.0 exactly; must not be ceil'd
    # to a whole headcount the way consumable quantities are.
    assert out["staffing"]["physicians"]["quantity"] == 1.0


def test_behavioral_health_staffing_is_driven_by_condition_caseload():
    out = rp.predict_resources(_county(), 30, config=CFG, state_summary={})

    # annual diabetes cases = 200 / 100 cases-per-fte = 2.0.
    assert out["staffing"]["behavioral_health_specialists"]["quantity"] == 2.0


# --- window scaling & reproducibility -----------------------------------------

def test_quantities_scale_proportionally_with_the_planning_window():
    out30 = rp.predict_resources(_county(), 30, config=CFG, state_summary={})
    out60 = rp.predict_resources(_county(), 60, config=CFG, state_summary={})

    assert out60["estimated_patient_volume"] == 2 * out30["estimated_patient_volume"]
    assert (out60["expected_encounters_by_condition"]["diabetes"]["expected_encounters"]
            == 2 * out30["expected_encounters_by_condition"]["diabetes"]["expected_encounters"])


def test_same_inputs_produce_identical_output():
    a = rp.predict_resources(_county(), 30, config=CFG, state_summary={})
    b = rp.predict_resources(_county(), 30, config=CFG, state_summary={})

    assert a == b


# --- three-tier fallback -------------------------------------------------------

def test_state_summary_averages_only_the_present_values():
    records = [{"outcomes": {"diabetes": 10.0}}, {"outcomes": {"diabetes": 20.0}}, {"outcomes": {}}]

    out = rp.state_summary(records, fields=["outcomes.diabetes"])

    assert out["outcomes.diabetes"] == 15.0


def test_missing_county_value_falls_back_to_the_state_mean():
    county = _county()
    county["outcomes"] = {}  # no county-level diabetes prevalence

    out = rp.predict_resources(county, 30, config=CFG, state_summary={"outcomes.diabetes": 25.0})

    assert out["expected_encounters_by_condition"]["diabetes"]["prevalence_pct"] == 25.0
    assert out["expected_encounters_by_condition"]["diabetes"]["prevalence_tier"] == "state"
    assert out["fallbacks_used"]["outcomes.diabetes"] == "state"


def test_missing_county_and_state_value_falls_back_to_the_config_default():
    county = _county()
    county["outcomes"] = {}

    out = rp.predict_resources(county, 30, config=CFG, state_summary={})

    assert out["expected_encounters_by_condition"]["diabetes"]["prevalence_pct"] == 10.0  # CFG default
    assert out["expected_encounters_by_condition"]["diabetes"]["prevalence_tier"] == "default"


# --- confidence and priority ---------------------------------------------------

def test_confidence_is_high_when_every_checked_field_is_county_observed():
    out = rp.predict_resources(_county(), 30, config=CFG, state_summary={})

    assert out["confidence_level"] == "High"
    assert out["confidence_detail"]["fields_from_fallback"] == 0


def test_confidence_degrades_as_fields_go_missing():
    sparse = {"id": "51998", "name": "Sparse County", "patients": 1000}

    out = rp.predict_resources(sparse, 30, config=CFG, state_summary={})

    assert out["confidence_level"] == "Low"
    assert out["confidence_detail"]["fields_from_fallback"] == 4


def test_priority_reaches_critical_at_the_top_of_every_weighted_input():
    county = _county(needIndex=100.0, hpsaScore=26, sdoh={"uninsured_rate": 100.0})

    out = rp.predict_resources(county, 30, config=CFG, state_summary={})

    assert out["priority_level"] == "Critical"
    assert out["priority_score"] == 90.0


def test_priority_factors_name_every_weighted_input():
    out = rp.predict_resources(_county(), 30, config=CFG, state_summary={})

    joined = " ".join(out["priority_factors"])
    assert "Unmet-need index" in joined
    assert "HPSA shortage score" in joined
    assert "Uninsured rate" in joined


# --- overrides (human-in-the-loop correction) ----------------------------------

def test_override_replaces_the_factor_and_is_flagged():
    out = rp.predict_resources(
        _county(), 30, config=CFG, state_summary={},
        overrides={"medications.diabetes_medications_and_insulin.fills_per_encounter": 2.0},
    )
    item = out["medications"]["diabetes_medications_and_insulin"]

    assert item["quantity"] == 132  # 66 * 2.0
    assert item["overridden"] is True


def test_untouched_items_are_not_flagged_as_overridden():
    out = rp.predict_resources(
        _county(), 30, config=CFG, state_summary={},
        overrides={"medications.diabetes_medications_and_insulin.fills_per_encounter": 2.0},
    )

    assert out["medications"]["vaccines"]["overridden"] is False


# --- missing population: graceful degradation ----------------------------------

def test_missing_population_returns_insufficient_data_not_a_crash():
    county = _county(patients=0)

    out = rp.predict_resources(county, 30, config=CFG, state_summary={})

    assert out["status"] == rp.INSUFFICIENT_DATA
    assert out["medications"] == {}
    assert out["priority_level"] is None
    assert "No population" in out["explanation"][0]


def test_none_population_also_returns_insufficient_data():
    county = _county(patients=None)

    out = rp.predict_resources(county, 30, config=CFG, state_summary={})

    assert out["status"] == rp.INSUFFICIENT_DATA


# --- export ----------------------------------------------------------------------

def test_csv_rows_cover_every_category():
    out = rp.predict_resources(_county(), 30, config=CFG, state_summary={})

    rows = rp.to_csv_rows(out)
    categories = {r["category"] for r in rows}

    assert categories == {"medications", "medical_supplies", "diagnostic_equipment", "staffing"}
    assert len(rows) == 2 + 2 + 3 + 2  # matches CFG's item counts per category


def test_export_csv_has_a_header_and_one_row_per_item():
    out = rp.predict_resources(_county(), 30, config=CFG, state_summary={})

    text = rp.to_export_csv(out)
    lines = text.strip().splitlines()

    assert lines[0].startswith("county_fips,")
    assert len(lines) == 1 + len(rp.to_csv_rows(out))


def test_export_csv_of_an_insufficient_data_result_is_empty():
    out = rp.predict_resources(_county(patients=0), 30, config=CFG, state_summary={})

    assert rp.to_export_csv(out) == ""


# --- disclosure ------------------------------------------------------------------

def test_every_prediction_carries_the_disclaimer_and_scope_note():
    out = rp.predict_resources(_county(), 30, config=CFG, state_summary={})

    assert "not a procurement instruction" in out["disclaimer"]
    assert "not one specific clinic" in out["scope_note"]


def test_review_status_reports_pending_by_default():
    status = rp.review_status(CFG)

    assert status["clinical_review"] == "pending"
    assert status["note"] == "note"


# --- the shipped config -----------------------------------------------------------

STORY_MEDICATIONS = {
    "hypertension_medications", "diabetes_medications_and_insulin", "cholesterol_medications",
    "asthma_inhalers", "antibiotics", "pain_management_medications", "vaccines",
}
STORY_SUPPLIES = {
    "syringes", "needles", "gloves", "masks", "ppe", "bandages",
    "iv_supplies", "test_strips", "specimen_collection_kits",
}
STORY_EQUIPMENT = {
    "blood_pressure_cuffs", "glucose_monitors", "pulse_oximeters",
    "ecg_equipment", "point_of_care_testing_supplies",
}
STORY_STAFFING = {
    "physicians", "nurse_practitioners", "registered_nurses",
    "medical_assistants", "behavioral_health_specialists", "care_coordinators",
}


def test_shipped_config_parses_and_declares_a_version():
    cfg = rp.load_config()

    assert cfg["version"] == 1
    assert cfg["planning_windows_days"] == [30, 60, 90]


def test_shipped_config_has_every_story_medication_category():
    assert set(rp.load_config()["medications"]) == STORY_MEDICATIONS


def test_shipped_config_has_every_story_supply_category():
    assert set(rp.load_config()["medical_supplies"]) == STORY_SUPPLIES


def test_shipped_config_has_every_story_equipment_category():
    assert set(rp.load_config()["diagnostic_equipment"]) == STORY_EQUIPMENT


def test_shipped_config_has_every_story_staffing_role():
    assert set(rp.load_config()["staffing"]) == STORY_STAFFING


def test_shipped_config_is_flagged_pending_clinical_review():
    status = rp.review_status()

    assert status["clinical_review"] == "pending"
    assert "not by a clinician" in status["note"]


def test_shipped_config_factors_are_all_positive():
    cfg = rp.load_config()
    for key, spec in cfg["medications"].items():
        factor = spec.get("fills_per_encounter") or spec.get("doses_per_percent_gap_per_patient")
        assert factor and factor > 0, f"medications.{key} has no positive factor"
    for key, spec in cfg["medical_supplies"].items():
        factor = spec.get("per_encounter") or spec.get("per_case_encounter")
        assert factor and factor > 0, f"medical_supplies.{key} has no positive factor"
    for key, spec in cfg["staffing"].items():
        factor = spec.get("patients_per_fte") or spec.get("cases_per_fte")
        assert factor and factor > 0, f"staffing.{key} has no positive factor"


def test_shipped_config_loader_reports_a_missing_file():
    from pathlib import Path

    with pytest.raises(FileNotFoundError, match="Missing resource planning config"):
        rp.load_config(Path("/nonexistent/resource_planning_config.yml"))


def test_predict_resources_runs_against_a_real_atlas_record():
    atlas_path = REPO_ROOT / "dashboard" / "data" / "clinic_atlas.json"
    if not atlas_path.exists():
        pytest.skip("no built clinic_atlas.json in this checkout")

    records = json.loads(atlas_path.read_text(encoding="utf-8"))["records"]
    cfg = rp.load_config()
    ss = rp.state_summary(records, config=cfg)

    out = rp.predict_resources(records[0], 30, config=cfg, state_summary=ss)

    assert out["status"] == rp.OK
    assert out["estimated_patient_volume"] > 0
    assert set(out["medications"]) == STORY_MEDICATIONS
    assert set(out["medical_supplies"]) == STORY_SUPPLIES
    assert set(out["diagnostic_equipment"]) == STORY_EQUIPMENT
    assert set(out["staffing"]) == STORY_STAFFING
    assert out["priority_level"] in ("Low", "Medium", "High", "Critical")
    assert out["confidence_level"] in ("Low", "Medium", "High")
