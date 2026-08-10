"""Regression tests for src/build_dataset.build() (fixture-driven, no network).

Locks in three bug fixes:
- a legitimate 0.0 domain score must survive (was rewritten to 50 by `or 50.0`)
- a multi-row-per-county source must not multiply the county spine on merge
- a missing population column must degrade cleanly (pop_max NaN crashed json.dumps)
plus the honesty contract: RealSource.extract() raises rather than fabricating.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

import src.build_dataset as bd
from src.catalog import Catalog
from src.ingestion.base import Provenance
from src.ingestion.registry import REGISTRY

COUNTIES = ["51001", "51003"]


def _fake_frames() -> dict[str, pd.DataFrame]:
    # 51001: 2021 is the most recent year, and Diabetes has the higher rate
    # that year (10.0 vs Asthma's 3.0) despite Asthma winning in 2020 -- this
    # is what locks in "most recent year, not all-time max".
    # 51003: no rows at all -> chronicDiseaseRisk must come back None, not a
    # fabricated 0.0.
    chronic = pd.DataFrame(
        [
            {"county_fips": "51001", "year": 2020, "condition": "Asthma", "rate": 9.0},
            {"county_fips": "51001", "year": 2020, "condition": "Diabetes", "rate": 1.0},
            {"county_fips": "51001", "year": 2021, "condition": "Asthma", "rate": 3.0},
            {"county_fips": "51001", "year": 2021, "condition": "Diabetes", "rate": 10.0},
        ]
    )
    return {
        "cdc_places": pd.DataFrame(
            {"county_fips": COUNTIES, "diabetes": [10.0, 12.0]}
        ),
        "cdc_eji": pd.DataFrame(
            {
                "county_fips": COUNTIES,
                # A county genuinely at the 0th percentile: legit 0.0 score.
                "environmental_burden_percentile": [0.0, 80.0],
            }
        ),
        "virginia_chronic_disease_hospitalization": chronic,
        # Only 51001 has a designated mental/dental shortage area; 51003 must
        # come back None (no fabricated 0/50), same missing-vs-zero contract
        # as every other real field.
        "hrsa_hpsa_mental_health": pd.DataFrame(
            {"county_fips": ["51001"], "mental_health_hpsa_score": [14.0]}
        ),
        "hrsa_hpsa_dental_health": pd.DataFrame(
            {"county_fips": ["51001"], "dental_health_hpsa_score": [11.0]}
        ),
    }


def _fake_site_counts() -> dict[str, dict[str, int]]:
    # 51003 is present with explicit zeros (a real "we checked, none here"
    # answer), distinct from a county absent from the dict entirely.
    return {
        "51001": {"grantee": 3, "rural_clinic": 1},
        "51003": {"grantee": 0, "rural_clinic": 0},
    }


@pytest.fixture()
def built(monkeypatch):
    frames = _fake_frames()

    def fake_run_source(cls, catalog, counties, refresh):
        if cls.provenance == Provenance.STUB:
            return None, Provenance.STUB
        if cls.source_id == "synthetic_clinical_dataset":
            return None, Provenance.SYNTHETIC
        df = frames.get(cls.source_id)
        return (df, Provenance.REAL) if df is not None else (None, "unavailable")

    monkeypatch.setattr(bd, "_run_source", fake_run_source)
    # _site_counts_by_county() reads dashboard/data/clinic_sites.json directly
    # rather than going through _run_source; stub it too so this fixture
    # doesn't depend on that file's real, changing content.
    monkeypatch.setattr(bd, "_site_counts_by_county", _fake_site_counts)
    return bd.build()


def test_one_record_per_county_despite_multirow_source(built):
    assert [r["id"] for r in built["records"]] == COUNTIES
    assert built["county_count"] == len(COUNTIES)


def test_zero_domain_score_survives(built):
    by_id = {r["id"]: r for r in built["records"]}

    assert by_id["51001"]["dom"]["environment"] == 0.0
    assert by_id["51003"]["dom"]["environment"] == 80.0


def test_missing_population_degrades_without_nan(built):
    # pop_max guard: Series([]).max() is NaN and NaN is truthy.
    json.dumps(built, allow_nan=False)

    assert all(r["patients"] == 0 for r in built["records"])


def test_unwired_measures_are_badged_stub(built):
    assert built["provenance"]["measures"] == {
        "source_id": "hrsa_uds",
        "status": "stub",
    }


def test_new_hpsa_fields_populate_and_missing_stays_none(built):
    by_id = {r["id"]: r for r in built["records"]}

    assert by_id["51001"]["hpsaScoreMentalHealth"] == 14.0
    assert by_id["51001"]["hpsaScoreDental"] == 11.0
    # 51003 has no designated shortage area for either discipline: None, not 0.
    assert by_id["51003"]["hpsaScoreMentalHealth"] is None
    assert by_id["51003"]["hpsaScoreDental"] is None


def test_chronic_disease_risk_uses_most_recent_year_and_highest_rate(built):
    by_id = {r["id"]: r for r in built["records"]}

    # 2020's max was Asthma (9.0); 2021 (the most recent year) flips it to
    # Diabetes (10.0 vs Asthma's 3.0) -- proves this reads the latest year,
    # not an all-time max across years.
    assert by_id["51001"]["chronicDiseaseRisk"] == {
        "leadingCondition": "Diabetes", "rate": 10.0, "asOfYear": 2021,
    }


def test_chronic_disease_risk_is_none_without_any_hospitalization_rows(built):
    by_id = {r["id"]: r for r in built["records"]}

    assert by_id["51003"]["chronicDiseaseRisk"] is None


def test_site_counts_flow_into_records(built):
    by_id = {r["id"]: r for r in built["records"]}

    assert by_id["51001"]["fqhcSiteCount"] == 3
    assert by_id["51001"]["ruralClinicCount"] == 1
    # Explicit zero from the source, not an absence.
    assert by_id["51003"]["fqhcSiteCount"] == 0
    assert by_id["51003"]["ruralClinicCount"] == 0


def test_new_fields_are_provenance_traceable(built):
    prov = built["provenance"]

    assert prov["hpsaScoreMentalHealth"]["source_id"] == "hrsa_hpsa_mental_health"
    assert prov["hpsaScoreDental"]["source_id"] == "hrsa_hpsa_dental_health"
    assert prov["fqhcSiteCount"]["source_id"] == "hrsa_hscd_sites"
    assert prov["ruralClinicCount"]["source_id"] == "cms_hcris_rhc"
    assert prov["fqhcSiteCount"]["status"] == Provenance.REAL


# --- _chronic_risk_by_county in isolation --------------------------------------

def test_chronic_risk_by_county_empty_frame_returns_empty_dict():
    assert bd._chronic_risk_by_county(None) == {}
    assert bd._chronic_risk_by_county(pd.DataFrame()) == {}


def test_chronic_risk_by_county_skips_a_county_whose_latest_year_is_all_nan():
    df = pd.DataFrame([
        {"county_fips": "51001", "year": 2021, "condition": "Asthma", "rate": float("nan")},
    ])

    assert bd._chronic_risk_by_county(df) == {}


# --- _site_counts_by_county in isolation ----------------------------------------

def test_site_counts_by_county_aggregates_by_kind(monkeypatch, tmp_path):
    sites_path = tmp_path / "clinic_sites.json"
    sites_path.write_text(json.dumps({"sites": [
        {"county_fips": "51001", "kind": "grantee"},
        {"county_fips": "51001", "kind": "grantee"},
        {"county_fips": "51001", "kind": "rural_clinic"},
        {"county_fips": "51003", "kind": "grantee"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(bd, "CLINIC_SITES_PATH", sites_path)

    counts = bd._site_counts_by_county()

    assert counts == {
        "51001": {"grantee": 2, "rural_clinic": 1},
        "51003": {"grantee": 1},
    }


def test_site_counts_by_county_returns_none_when_file_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(bd, "CLINIC_SITES_PATH", tmp_path / "does_not_exist.json")

    assert bd._site_counts_by_county() is None


def test_site_counts_by_county_returns_none_on_malformed_json(monkeypatch, tmp_path):
    sites_path = tmp_path / "clinic_sites.json"
    sites_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(bd, "CLINIC_SITES_PATH", sites_path)

    assert bd._site_counts_by_county() is None


def test_real_sources_raise_rather_than_fabricate(monkeypatch, tmp_path):
    """With no raw data available, extract() must raise -- never invent rows."""
    import src.ingestion.base as base
    import src.ingestion.cdc_eji as cdc_eji
    import src.ingestion.virginia_chronic_disease_hospitalization as vchronic

    monkeypatch.setattr(base, "RAW_DIR", tmp_path)
    monkeypatch.setattr(vchronic, "REPO_ROOT", tmp_path)
    # cdc_eji reads a committed reference table rather than a raw cache.
    monkeypatch.setattr(cdc_eji, "ENVIRONMENT_REF", tmp_path / "missing.csv")

    catalog = Catalog.load()

    for cls in REGISTRY.values():
        if cls.provenance != Provenance.REAL:
            continue

        source = cls(catalog)

        with pytest.raises(Exception):
            frame = source.extract()
            pytest.fail(f"{cls.source_id}.extract() fabricated {len(frame)} rows")
