"""Census ACS 5-year SDoH indicators -> economic + education domains.

Emits raw county indicators; normalization to 0-100 happens in the build.
Needs CENSUS_API_KEY (per the catalog). county_fips = state(2) + county(3).
"""

from __future__ import annotations

import os

import pandas as pd

from src.ingestion._census import census_json as _census_json
from src.ingestion.base import RealSource, TARGET_STATE_FIPS

ACS_YEAR = "2022"
# ACS Data Profile variable -> output column.
VARIABLES = {
    "DP03_0119PE": "poverty_rate",
    "DP03_0099PE": "uninsured_rate",
    "DP03_0009PE": "unemployment_rate",
    "DP03_0062E": "median_household_income",
    "DP02_0067PE": "pct_hs_or_higher",
}


class CensusAcs(RealSource):
    source_id = "census_acs_sdoh"

    def fetch_raw(self) -> None:
        endpoint = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5/profile"
        params = {"get": "NAME," + ",".join(VARIABLES),
                  "for": "county:*", "in": f"state:{TARGET_STATE_FIPS}"}
        key = os.environ.get(self.entry.get("api_key_env_var") or "CENSUS_API_KEY")
        if key:
            params["key"] = key
        rows = _census_json(endpoint, params)
        pd.DataFrame(rows[1:], columns=rows[0]).to_csv(self.raw_path, index=False)

    def extract(self) -> pd.DataFrame:
        df = pd.read_csv(self.raw_path, dtype={"state": str, "county": str})
        df["county_fips"] = df["state"].str.zfill(2) + df["county"].str.zfill(3)
        df = df.rename(columns=VARIABLES)
        for col in VARIABLES.values():
            df[col] = pd.to_numeric(df[col], errors="coerce")
        # Share of adults without a high-school diploma.
        df["pct_no_hs_diploma"] = 100 - df["pct_hs_or_higher"]
        return df[["county_fips", "poverty_rate", "uninsured_rate", "unemployment_rate",
                   "median_household_income", "pct_no_hs_diploma"]]
