"""Regression tests for the county-name matching bug fix in
src/ingestion/virginia_chronic_disease_hospitalization.py.

Before the fix, _normalize_county_name's unanchored, case-sensitive regex
never actually stripped "County"/"City" from the CSV's capitalization, so
every row silently failed to join to a county_fips and this frame always
returned zero rows -- masked because build_dataset.py excludes this frame
from the county merge, so nothing downstream ever inspected it.
"""

from __future__ import annotations

import json

import pytest

import src.ingestion.virginia_chronic_disease_hospitalization as vchronic
from src.ingestion.virginia_chronic_disease_hospitalization import (
    RETIRED_COUNTY_FIPS,
    _county_fips_lookup,
    _normalize_county_name,
)


@pytest.mark.parametrize("raw,expected", [
    ("Accomack County", "accomack"),
    ("Richmond city", "richmond"),
    ("Charles City County", "charles city"),  # "City" is part of the proper name
    ("James City County", "james city"),
    ("Bedford", "bedford"),  # no suffix at all
])
def test_normalize_county_name_strips_only_the_trailing_type_suffix(raw, expected):
    assert _normalize_county_name(raw) == expected


def _write_geojson(path, features):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")


def test_county_fips_lookup_excludes_the_retired_bedford_city_code(monkeypatch, tmp_path):
    monkeypatch.setattr(vchronic, "REPO_ROOT", tmp_path)
    geo_path = tmp_path / "dashboard" / "data" / "va-counties.geojson"
    _write_geojson(geo_path, [
        {"properties": {"name": "Bedford", "county_fips": "51019"}},   # real county
        {"properties": {"name": "Bedford", "county_fips": "51515"}},   # retired independent city
        {"properties": {"name": "Accomack", "county_fips": "51001"}},
    ])

    lookup = _county_fips_lookup()

    assert lookup["bedford"] == "51019"
    assert "51515" not in lookup.values()
    assert lookup["accomack"] == "51001"


def test_retired_county_fips_constant_names_bedford_city():
    # Documents *why* 51515 is excluded, so a future editor doesn't delete the
    # guard thinking it's dead code.
    assert RETIRED_COUNTY_FIPS == {"51515"}
