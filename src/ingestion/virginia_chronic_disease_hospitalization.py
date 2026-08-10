"""Virginia chronic disease hospitalization dataset integrated through the repo's ingestion pattern."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import requests

from src.catalog import REPO_ROOT
from src.ingestion.base import RealSource, TARGET_STATE_FIPS


def _normalize_county_name(value: str) -> str:
    # Anchored to the trailing "County"/"City" suffix, case-insensitively: an
    # unanchored \b(county|city)\b also stripped "City" out of counties whose
    # proper name contains it ("Charles City County" -> "charles", not
    # "charles city"), and being case-sensitive meant "County" (the CSV's
    # capitalization) never matched at all, so every row silently fell out of
    # the join instead of raising -- this frame was returning zero rows.
    return re.sub(r"\s+(county|city)\s*$", "", str(value or ""), flags=re.IGNORECASE).strip().lower()


# 51515 (Bedford, an independent city) was retired in July 2013 and merged
# into Bedford County (51019). dashboard/data/va-counties.geojson still
# carries a stale feature for it, also named "Bedford" -- without this guard,
# whichever of the two features iterates last silently wins the "bedford" key
# in the lookup below, and "Bedford County" hospitalization rows have a
# roughly 50/50 chance of being attributed to the retired code instead of the
# real county (growing the county count to 134 and violating the
# five-digit-standardized-FIPS convention the rest of the atlas relies on).
RETIRED_COUNTY_FIPS = {"51515"}


def _county_fips_lookup() -> dict[str, str]:
    geo_path = REPO_ROOT / "dashboard" / "data" / "va-counties.geojson"
    if not geo_path.exists():
        return {}
    with geo_path.open("r", encoding="utf-8") as fh:
        geo = json.load(fh)

    lookup: dict[str, str] = {}
    for feature in geo.get("features", []):
        props = feature.get("properties", {})
        county_name = props.get("name")
        county_fips = props.get("county_fips")
        if county_fips in RETIRED_COUNTY_FIPS:
            continue
        if county_name and county_fips:
            lookup[_normalize_county_name(county_name)] = str(county_fips).zfill(5)
    return lookup


class VirginiaChronicDiseaseHospitalization(RealSource):
    source_id = "virginia_chronic_disease_hospitalization"

    @property
    def raw_path(self) -> Path:
        return REPO_ROOT / "data" / "raw" / f"{self.source_id}.csv"

    def fetch_raw(self) -> None:
        resource_id = self.access_url.rstrip("/").split("/resource/")[-1]
        endpoint = (
            "https://data.virginia.gov/api/3/action/datastore_search"
            f"?resource_id={resource_id}&limit=50000"
        )
        resp = requests.get(endpoint, timeout=120)
        resp.raise_for_status()
        payload = resp.json()
        records = payload.get("result", {}).get("records", [])
        if not records:
            raise ValueError(f"No records returned for {resource_id}")
        pd.DataFrame(records).to_csv(self.raw_path, index=False)

    def extract(self) -> pd.DataFrame:
        df = pd.read_csv(self.raw_path, dtype={"Geography": str, "Indicator": str})
        if df.empty:
            return pd.DataFrame(columns=["county_fips", "county", "year", "condition", "cases", "rate"])

        lookup = _county_fips_lookup()
        df = df.rename(columns={
            "Geography": "county",
            "Indicator": "condition",
            "Hospitalization Count": "cases",
            "Age-Adjusted Rate per 100,000": "rate",
            "Year": "year",
        })

        df["county"] = df["county"].fillna("").astype(str).str.strip()
        df["county_fips"] = df["county"].map(lambda name: lookup.get(_normalize_county_name(name)))
        df = df[df["county_fips"].notna()].copy()

        df["county_fips"] = df["county_fips"].astype(str).str.zfill(5)
        df = df[df["county_fips"].str.startswith(TARGET_STATE_FIPS)].copy()
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df["cases"] = pd.to_numeric(df["cases"], errors="coerce").fillna(0)
        df["rate"] = pd.to_numeric(df["rate"], errors="coerce").fillna(0)

        return df[["county_fips", "county", "year", "condition", "cases", "rate"]].reset_index(drop=True)
