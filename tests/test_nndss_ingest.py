"""US-048: CDC NNDSS weekly surveillance ingestion.

Fixture-driven and offline, following tests/test_model.py.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.catalog import Catalog
from src.ingestion.cdc_nndss import (
    CdcNndss,
    TARGET_JURISDICTION,
    _STATE_PREDICATE,
    _assert_condition_week_keyed,
    _socrata_id,
)


def _raw(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{"m1_flag": "-", **r} for r in rows])


def test_clean_renames_and_types_the_series_key():
    out = CdcNndss._clean(_raw([
        {"year": "2024", "week": "7", "label": "Pertussis", "m1": "12"},
    ]))

    assert list(out.columns) == ["jurisdiction", "condition", "mmwr_year", "mmwr_week", "cases"]
    row = out.iloc[0]
    assert row["condition"] == "Pertussis"
    assert int(row["mmwr_year"]) == 2024
    assert int(row["mmwr_week"]) == 7
    assert row["cases"] == 12


@pytest.mark.parametrize("flag", ["N", "U", "NC"])
def test_flagged_rows_become_null_not_zero(flag):
    # A suppressed week is unknown; zeroing it would teach the model that
    # surveillance gaps are quiet periods.
    out = CdcNndss._clean(_raw([
        {"year": "2024", "week": "3", "label": "Shigellosis", "m1": "5", "m1_flag": flag},
    ]))

    assert out["cases"].isna().all()


def test_unflagged_zero_is_preserved():
    out = CdcNndss._clean(_raw([
        {"year": "2024", "week": "3", "label": "Anthrax", "m1": "0"},
    ]))

    assert out["cases"].iloc[0] == 0


def test_reissued_week_keeps_the_latest_row():
    out = CdcNndss._clean(_raw([
        {"year": "2025", "week": "10", "label": "Gonorrhea", "m1": "200"},
        {"year": "2025", "week": "10", "label": "Gonorrhea", "m1": "231"},
    ]))

    assert len(out) == 1
    assert out["cases"].iloc[0] == 231


def test_clean_drops_rows_missing_the_series_key():
    out = CdcNndss._clean(_raw([
        {"year": "2024", "week": "1", "label": "Campylobacteriosis", "m1": "30"},
        {"year": None, "week": "2", "label": "Campylobacteriosis", "m1": "31"},
        {"year": "2024", "week": "3", "label": "", "m1": "32"},
    ]))

    assert len(out) == 1
    assert out["condition"].iloc[0] == "Campylobacteriosis"


def test_clean_raises_when_a_required_column_is_absent():
    with pytest.raises(ValueError, match="missing required column"):
        CdcNndss._clean(pd.DataFrame([{"year": "2024", "week": "1"}]))


def test_output_is_unique_per_condition_week():
    out = CdcNndss._clean(_raw([
        {"year": "2024", "week": w, "label": c, "m1": "1"}
        for c in ("Pertussis", "Shigellosis")
        for w in ("1", "2", "3")
    ]))

    _assert_condition_week_keyed(out)
    assert len(out) == 6


def test_key_assertion_rejects_duplicate_condition_weeks():
    dupes = pd.DataFrame([
        {"condition": "Pertussis", "mmwr_year": 2024, "mmwr_week": 5, "cases": 1},
        {"condition": "Pertussis", "mmwr_year": 2024, "mmwr_week": 5, "cases": 2},
    ])

    with pytest.raises(ValueError, match="duplicate"):
        _assert_condition_week_keyed(dupes)


def test_state_filter_is_case_insensitive():
    # CDC writes "VIRGINIA" pre-2025 and "Virginia" after; an equality filter
    # would silently drop the two most recent years.
    predicate = _STATE_PREDICATE.format(jurisdiction=TARGET_JURISDICTION)

    assert "upper(states)" in predicate
    assert TARGET_JURISDICTION.isupper()


def test_socrata_id_is_the_last_path_segment():
    assert _socrata_id("https://data.cdc.gov/NNDSS/NNDSS-Weekly-Data/x9gk-5huc") == "x9gk-5huc"
    assert _socrata_id("https://data.cdc.gov/NNDSS/NNDSS-Weekly-Data/x9gk-5huc/") == "x9gk-5huc"


def test_source_is_bound_to_a_real_catalog_entry():
    source = CdcNndss(Catalog.load())

    assert source.source_id == "cdc_nndss"
    assert _socrata_id(source.access_url) == "x9gk-5huc"


def test_nndss_is_absent_from_the_county_registry():
    # State-keyed data must not enter build_dataset's county-wide merge.
    from src.ingestion.registry import REGISTRY

    assert "cdc_nndss" not in REGISTRY
