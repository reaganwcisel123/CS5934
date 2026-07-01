"""County population totals -> patients denominator / county_population_total.

PEP's standalone API is deprecated for recent vintages, so we read total
population from ACS 5-year (B01003_001E). Same county keys, real Census data.
"""

from __future__ import annotations

import os

import pandas as pd

from src.ingestion._census import census_json as _census_json
from src.ingestion.base import RealSource, TARGET_STATE_FIPS

ACS_YEAR = "2022"
POP_VAR = "B01003_001E"  # total population


class CensusPep(RealSource):
    source_id = "county_population_estimates"

    def fetch_raw(self) -> None:
        endpoint = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
        params = {"get": f"NAME,{POP_VAR}", "for": "county:*",
                  "in": f"state:{TARGET_STATE_FIPS}"}
        key = os.environ.get(self.entry.get("api_key_env_var") or "CENSUS_API_KEY")
        if key:
            params["key"] = key
        rows = _census_json(endpoint, params)
        pd.DataFrame(rows[1:], columns=rows[0]).to_csv(self.raw_path, index=False)

    def extract(self) -> pd.DataFrame:
        df = pd.read_csv(self.raw_path, dtype={"state": str, "county": str})
        df["county_fips"] = df["state"].str.zfill(2) + df["county"].str.zfill(3)
        df["county_population_total"] = pd.to_numeric(df[POP_VAR], errors="coerce")
        df["county_name"] = df["NAME"].str.replace(", Virginia", "", regex=False)
        return df[["county_fips", "county_name", "county_population_total"]]
