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
    chronic = pd.DataFrame(
        [
            {"county_fips": fips, "year": year, "condition": cond, "rate": 1.0}
            for fips in COUNTIES
            for year in (2020, 2021)
            for cond in ("Asthma", "Diabetes")
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
