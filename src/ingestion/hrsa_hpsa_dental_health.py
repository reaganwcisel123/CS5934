"""HRSA Dental Health HPSA -> per-county shortage score (keyless CSV).

Sibling of hrsa_hpsa.py (Primary Care); see hrsa_hpsa_mental_health.py's
docstring for why this duplicates rather than imports the shared shape.
"""

from __future__ import annotations

import pandas as pd
import requests

from src.ingestion.base import RealSource, TARGET_STATE_FIPS

HRSA_DH_HPSA_CSV = "https://data.hrsa.gov/DataDownload/DD_Files/BCD_HPSA_FCT_DET_DH.csv"
COL_SCORE, COL_FIPS = "HPSA Score", "Common State County FIPS Code"
COL_STATUS, COL_DISCIPLINE = "HPSA Status", "HPSA Discipline Class"


class HrsaHpsaDentalHealth(RealSource):
    source_id = "hrsa_hpsa_dental_health"

    def fetch_raw(self) -> None:
        resp = requests.get(HRSA_DH_HPSA_CSV, timeout=120)
        resp.raise_for_status()
        self.raw_path.write_bytes(resp.content)

    def extract(self) -> pd.DataFrame:
        # Keep designated dental-health areas; average the HPSA score per county.
        df = pd.read_csv(self.raw_path, dtype={COL_FIPS: str}, low_memory=False)
        df = df[df[COL_STATUS].astype(str).str.contains("Designated", case=False, na=False)]
        if COL_DISCIPLINE in df.columns:
            df = df[df[COL_DISCIPLINE].astype(str).str.contains("Dental Health", case=False, na=False)]
        df["county_fips"] = df[COL_FIPS].str.zfill(5)
        df = df[df["county_fips"].str.startswith(TARGET_STATE_FIPS)].copy()
        df[COL_SCORE] = pd.to_numeric(df[COL_SCORE], errors="coerce")
        return (df.groupby("county_fips")[COL_SCORE].mean().round().reset_index()
                  .rename(columns={COL_SCORE: "dental_health_hpsa_score"}))
