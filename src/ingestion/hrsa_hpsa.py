"""HRSA Primary Care HPSA -> care-access domain + hpsaScore (keyless CSV)."""

from __future__ import annotations

import pandas as pd
import requests

from src.ingestion.base import RealSource, TARGET_STATE_FIPS

HRSA_PC_HPSA_CSV = "https://data.hrsa.gov/DataDownload/DD_Files/BCD_HPSA_FCT_DET_PC.csv"
# Column names per HRSA's export; verify here if HRSA renames them.
COL_SCORE, COL_FIPS = "HPSA Score", "Common State County FIPS Code"
COL_STATUS, COL_DISCIPLINE = "HPSA Status", "HPSA Discipline Class"


class HrsaHpsa(RealSource):
    source_id = "hrsa_hpsa"

    def fetch_raw(self) -> None:
        resp = requests.get(HRSA_PC_HPSA_CSV, timeout=120)
        resp.raise_for_status()
        self.raw_path.write_bytes(resp.content)

    def extract(self) -> pd.DataFrame:
        # Keep designated primary-care areas; average the HPSA score per county.
        df = pd.read_csv(self.raw_path, dtype={COL_FIPS: str}, low_memory=False)
        df = df[df[COL_STATUS].astype(str).str.contains("Designated", case=False, na=False)]
        if COL_DISCIPLINE in df.columns:
            df = df[df[COL_DISCIPLINE].astype(str).str.contains("Primary Care", case=False, na=False)]
        df["county_fips"] = df[COL_FIPS].str.zfill(5)
        df = df[df["county_fips"].str.startswith(TARGET_STATE_FIPS)]
        df[COL_SCORE] = pd.to_numeric(df[COL_SCORE], errors="coerce")
        return (df.groupby("county_fips")[COL_SCORE].mean().round().reset_index()
                  .rename(columns={COL_SCORE: "primary_care_hpsa_score"}))
