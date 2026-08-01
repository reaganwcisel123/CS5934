"""US-051: condition -> supply mapping, quantity ranges, and overrides."""

from __future__ import annotations

import pytest

from src.model import forecast_config as FC
from src.model import supply_needs as sn

MAP = {
    "conditions": {
        "Pertussis": {
            "rationale": "PCR plus contact prophylaxis.",
            "supplies": [
                {"item": "Pertussis PCR swab", "per_case": 1.5},
                {"item": "Azithromycin course", "per_case": 3.5, "note": "household PEP"},
            ],
        }
    }
}


def _forecast(**kw) -> dict:
    return {"condition": "Pertussis", "status": "ok", "point": 10.0, "lower": 4.0,
            "upper": 20.0, "horizon_weeks": 4, "weeks_stale": 0, **kw}


def test_quantities_scale_by_the_per_case_factor():
    out = sn.supply_needs([_forecast()], MAP)
    swab = out[0]["items"][0]

    assert swab["quantity_expected"] == 15   # ceil(10 * 1.5)
    assert swab["quantity_low"] == 6         # ceil(4 * 1.5)
    assert swab["quantity_high"] == 30       # ceil(20 * 1.5)


def test_quantities_round_up():
    # Under-stocking a clinic is worse than over-stocking it.
    out = sn.supply_needs([_forecast(point=3.0, lower=3.0, upper=3.0)], MAP)

    assert out[0]["items"][0]["quantity_expected"] == 5  # ceil(3 * 1.5) == 5


def test_range_is_derived_from_the_forecast_interval():
    out = sn.supply_needs([_forecast()], MAP)
    item = out[0]["items"][0]

    assert item["quantity_low"] <= item["quantity_expected"] <= item["quantity_high"]


def test_rationale_travels_with_every_mapped_condition():
    # A clinician has to be able to audit why a condition implies an item.
    out = sn.supply_needs([_forecast()], MAP)

    assert out[0]["rationale"] == "PCR plus contact prophylaxis."


def test_disclaimer_is_always_attached():
    out = sn.supply_needs([_forecast()], MAP)

    assert "not a procurement instruction" in out[0]["disclaimer"]


def test_unmapped_condition_is_surfaced_not_dropped():
    # A gap in the mapping file must not read as "nothing to stock".
    out = sn.supply_needs([_forecast(condition="Mumps")], MAP)

    assert len(out) == 1
    assert out[0]["status"] == sn.UNMAPPED
    assert out[0]["items"] == []


def test_unmapped_conditions_helper_lists_the_gaps():
    forecasts = [_forecast(), _forecast(condition="Mumps"), _forecast(condition="Measles")]

    assert sn.unmapped_conditions(forecasts, MAP) == ["Measles", "Mumps"]


def test_insufficient_history_yields_no_quantities():
    out = sn.supply_needs(
        [{"condition": "Pertussis", "status": "insufficient_history", "point": None,
          "lower": None, "upper": None}], MAP)

    assert out[0]["status"] == "insufficient_history"
    assert out[0]["items"] == []


def test_override_replaces_the_factor_and_is_flagged():
    # Human-in-the-loop: a clinic corrects a figure without editing shared config.
    out = sn.supply_needs([_forecast()], MAP,
                          overrides={"Pertussis::Pertussis PCR swab": 1.0})
    swab = out[0]["items"][0]

    assert swab["per_case"] == 1.0
    assert swab["overridden"] is True
    assert swab["quantity_expected"] == 10


def test_untouched_items_are_not_flagged_as_overridden():
    out = sn.supply_needs([_forecast()], MAP,
                          overrides={"Pertussis::Pertussis PCR swab": 1.0})

    assert out[0]["items"][1]["overridden"] is False


def test_item_notes_are_preserved():
    out = sn.supply_needs([_forecast()], MAP)

    assert out[0]["items"][1]["note"] == "household PEP"


# --- the shipped mapping file ------------------------------------------------

def test_shipped_map_parses_and_declares_a_version():
    # v2 added blurbs and the clinical_review flag (US-056).
    data = sn.load_supply_map()

    assert data["version"] == 2
    assert data["conditions"]


def test_every_shipped_entry_has_a_rationale_and_supplies():
    for condition, entry in sn.load_supply_map()["conditions"].items():
        assert entry.get("rationale"), f"{condition} is missing a rationale"
        assert entry.get("supplies"), f"{condition} has no supplies"


def test_every_shipped_supply_has_a_positive_per_case_factor():
    for condition, entry in sn.load_supply_map()["conditions"].items():
        for item in entry["supplies"]:
            assert item.get("item"), f"{condition} has an unnamed item"
            assert float(item["per_case"]) > 0, f"{condition}/{item['item']} is not positive"


def test_every_forecast_condition_is_mapped():
    # Guards the case where someone adds a condition to the forecast set and
    # forgets the supply mapping, which would silently render as "unmapped".
    mapped = set(sn.load_supply_map()["conditions"])
    missing = [c for c in FC.FORECAST_CONDITIONS if c not in mapped]

    assert missing == [], f"unmapped forecast conditions: {missing}"


def test_every_shipped_entry_has_a_cited_blurb():
    # A blurb without a source is an unsourced clinical claim.
    for condition, entry in sn.load_supply_map()["conditions"].items():
        blurb = (entry.get("blurb") or "").strip()
        assert blurb, f"{condition} is missing a blurb"
        assert "Source:" in blurb, f"{condition} blurb cites no source"


def test_shipped_map_is_flagged_pending_clinical_review():
    # Un-reviewed clinical guidance must not render as settled. If someone
    # flips this to approved, it should be a deliberate, reviewed act.
    status = sn.review_status()

    assert status["clinical_review"] == "pending"
    assert "not by a clinician" in status["note"]


def test_every_rankable_condition_has_a_blurb():
    # Guards the gap this epic exists to close: the ranking can surface any
    # reported condition, and one without guidance renders as 'unmapped'.
    import pandas as pd

    from src.model import threat_ranking as tr

    mapped = set(sn.load_supply_map()["conditions"])
    try:
        region = tr.load_region()
    except FileNotFoundError:
        pytest.skip("needs `python -m src.ingestion.cdc_nndss`")

    ranked = [t["condition"] for t in tr.rank_threats(region, top_n=10)]
    missing = [c for c in ranked if c not in mapped]

    assert missing == [], f"ranked but unmapped: {missing}"


def test_blurb_for_returns_none_on_an_unknown_condition():
    assert sn.blurb_for("Not A Real Condition", MAP) is None


def test_blurb_travels_with_the_supply_payload():
    out = sn.supply_needs([_forecast()], {"conditions": {
        "Pertussis": {"blurb": "Stock ahead. Source: CDC.", "rationale": "r",
                      "supplies": [{"item": "Swab", "per_case": 1.0}]}}})

    assert out[0]["blurb"] == "Stock ahead. Source: CDC."


def test_load_supply_map_reports_a_missing_file():
    from pathlib import Path

    with pytest.raises(FileNotFoundError, match="Missing supply map"):
        sn.load_supply_map(Path("/nonexistent/condition_supply_map.yml"))
