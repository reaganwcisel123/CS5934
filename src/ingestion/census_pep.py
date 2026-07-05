"""County population totals -> the patients denominator (county_population_total).

Reads the Census PEP county-totals bulk CSV (catalog access_url). Unlike the
Census API, this file download needs no key, so population is always real.
"""

from __future__ import annotations

import pandas as pd
import requests

from src.ingestion.base import RealSource, TARGET_STATE_FIPS


class CensusPep(RealSource):
    source_id = "county_population_estimates"

    def fetch_raw(self) -> None:
        # Keyless PEP bulk CSV (catalog access_url). Cache the upstream file as-is.
        resp = requests.get(self.access_url, timeout=120)
        resp.raise_for_status()
        self.raw_path.write_bytes(resp.content)

    def extract(self) -> pd.DataFrame:
        # The file is latin-1 and carries STATE/COUNTY FIPS as strings.
        df = pd.read_csv(self.raw_path, dtype={"STATE": str, "COUNTY": str},
                         encoding="latin-1")
        # County-equivalent rows only ('000' is the state total).
        df = df[(df["STATE"] == TARGET_STATE_FIPS) & (df["COUNTY"] != "000")].copy()
        # Newest vintage column, e.g. POPESTIMATE2024.
        pop_col = max(c for c in df.columns if c.startswith("POPESTIMATE"))
        df["county_fips"] = df["STATE"].str.zfill(2) + df["COUNTY"].str.zfill(3)
        df["county_population_total"] = pd.to_numeric(df[pop_col], errors="coerce")
        df["county_name"] = df["CTYNAME"]
        return df[["county_fips", "county_name", "county_population_total"]]
