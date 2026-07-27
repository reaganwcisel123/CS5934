"""Focused, offline tests for the County Health Rankings source adapter."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.catalog import Catalog
from src.ingestion.county_health_rankings import (
    CountyHealthRankings,
    CountyHealthRankingsSchemaError,
    normalize_county_fips,
    parse_percent,
    parse_population_per_provider,
)

FIXTURE = Path(__file__).parent / "fixtures" / "county_health_rankings.csv"


def _source(monkeypatch) -> CountyHealthRankings:
    monkeypatch.setenv("COUNTY_HEALTH_RANKINGS_PATH", str(FIXTURE))
    return CountyHealthRankings(Catalog.load())


def test_normalize_county_fips_pads_and_preserves_county_equivalents():
    assert normalize_county_fips(1) == "00001"
    assert normalize_county_fips("51710") == "51710"
    assert normalize_county_fips("not-a-fips") is None


def test_extract_removes_summary_rows_and_deduplicates_counties(monkeypatch):
    frame = _source(monkeypatch).run()

    assert set(frame["county_fips"]) == {"01001", "02001", "51710"}
    assert frame["county_fips"].is_unique
    # The deterministic rule keeps the first equally complete duplicate row.
    assert frame.loc[frame["county_fips"] == "01001", "preventable_hospital_stays"].item() == 1500


def test_extract_preserves_suppression_as_null_and_parses_percentages(monkeypatch):
    frame = _source(monkeypatch).run().set_index("county_fips")

    assert pd.isna(frame.at["51710", "preventable_hospital_stays"])
    assert frame.at["01001", "uninsured_percent"] == 11.0
    assert frame.at["51710", "broadband_access_percent"] == 75.0
    assert pd.isna(frame.at["02001", "primary_care_physician_burden"])


def test_ratio_and_percentage_parsing_supports_documented_forms():
    assert parse_population_per_provider("1,230:1") == 1230.0
    assert parse_population_per_provider("1230") == 1230.0
    assert parse_population_per_provider("0") is None
    assert parse_percent("0.81") == 81.0
    assert parse_percent("81%") == 81.0
    assert parse_percent("Suppressed") is None


def test_extract_requires_preventable_hospital_stays_column(tmp_path, monkeypatch):
    missing_target = tmp_path / "missing-target.csv"
    missing_target.write_text("fipscode,v003_rawvalue\n01001,0.1\n", encoding="utf-8")
    monkeypatch.setenv("COUNTY_HEALTH_RANKINGS_PATH", str(missing_target))

    with pytest.raises(CountyHealthRankingsSchemaError, match="preventable-hospital-stays"):
        CountyHealthRankings(Catalog.load()).run()
