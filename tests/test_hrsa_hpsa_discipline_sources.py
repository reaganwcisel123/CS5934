"""Discipline filtering for the HPSA mental-health / dental-health sources.

Both modules are siblings of src/ingestion/hrsa_hpsa.py (Primary Care),
duplicated rather than shared per the ingestion-independence contract -- these
tests lock in that each one filters to its own discipline, not another's, and
excludes non-designated rows, without touching the network.
"""

from __future__ import annotations

import pandas as pd
import pytest

import src.ingestion.base as base
from src.catalog import Catalog
from src.ingestion.hrsa_hpsa_dental_health import HrsaHpsaDentalHealth
from src.ingestion.hrsa_hpsa_mental_health import HrsaHpsaMentalHealth

RAW_ROWS = [
    {"HPSA Status": "Designated", "HPSA Discipline Class": "Mental Health",
     "HPSA Score": 14, "Common State County FIPS Code": "51001"},
    {"HPSA Status": "Designated", "HPSA Discipline Class": "Mental Health",
     "HPSA Score": 6, "Common State County FIPS Code": "51001"},
    {"HPSA Status": "Designated", "HPSA Discipline Class": "Dental Health",
     "HPSA Score": 11, "Common State County FIPS Code": "51001"},
    {"HPSA Status": "Withdrawn", "HPSA Discipline Class": "Mental Health",
     "HPSA Score": 20, "Common State County FIPS Code": "51001"},
    {"HPSA Status": "Designated", "HPSA Discipline Class": "Mental Health",
     "HPSA Score": 8, "Common State County FIPS Code": "37001"},  # out of state
]


@pytest.fixture()
def catalog(monkeypatch, tmp_path):
    # raw_path resolves against base.RAW_DIR at call time, so redirecting it
    # here keeps every test in this file off the real data/raw/ cache.
    monkeypatch.setattr(base, "RAW_DIR", tmp_path)
    return Catalog.load()


def _write_raw(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_mental_health_source_averages_only_designated_mental_health_rows(catalog):
    source = HrsaHpsaMentalHealth(catalog)
    _write_raw(source.raw_path, RAW_ROWS)

    out = source.extract()

    # (14 + 6) / 2 = 10; excludes the Withdrawn row (20) and the Dental row (11).
    assert out.set_index("county_fips")["mental_health_hpsa_score"].to_dict() == {"51001": 10.0}


def test_dental_health_source_only_keeps_dental_rows(catalog):
    source = HrsaHpsaDentalHealth(catalog)
    _write_raw(source.raw_path, RAW_ROWS)

    out = source.extract()

    assert out.set_index("county_fips")["dental_health_hpsa_score"].to_dict() == {"51001": 11.0}


def test_out_of_state_rows_are_excluded(catalog):
    source = HrsaHpsaMentalHealth(catalog)
    _write_raw(source.raw_path, RAW_ROWS)

    out = source.extract()

    assert "37001" not in set(out["county_fips"])
