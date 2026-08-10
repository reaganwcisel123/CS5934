"""HRSA Mental Health HPSA -> per-county shortage score (keyless CSV).

Sibling of hrsa_hpsa.py (Primary Care): HRSA publishes discipline-specific
HPSA exports at the same path pattern (_PC/_MH/_DH). Deliberately not shared
via import -- ingestion sources stay mutually independent (see
documents/architecture-boundaries.md) -- so this duplicates hrsa_hpsa.py's
~15-line extract shape rather than importing it.
"""

from __future__ import annotations

import pandas as pd
import requests

from src.ingestion.base import RealSource, TARGET_STATE_FIPS

HRSA_MH_HPSA_CSV = "https://data.hrsa.gov/DataDownload/DD_Files/BCD_HPSA_FCT_DET_MH.csv"
COL_SCORE, COL_FIPS = "HPSA Score", "Common State County FIPS Code"
COL_STATUS, COL_DISCIPLINE = "HPSA Status", "HPSA Discipline Class"


class HrsaHpsaMentalHealth(RealSource):
    source_id = "hrsa_hpsa_mental_health"

    def fetch_raw(self) -> None:
        resp = requests.get(HRSA_MH_HPSA_CSV, timeout=120)
        resp.raise_for_status()
        self.raw_path.write_bytes(resp.content)

    def extract(self) -> pd.DataFrame:
        # Keep designated mental-health areas; average the HPSA score per county.
        df = pd.read_csv(self.raw_path, dtype={COL_FIPS: str}, low_memory=False)
        df = df[df[COL_STATUS].astype(str).str.contains("Designated", case=False, na=False)]
        if COL_DISCIPLINE in df.columns:
            df = df[df[COL_DISCIPLINE].astype(str).str.contains("Mental Health", case=False, na=False)]
        df["county_fips"] = df[COL_FIPS].str.zfill(5)
        df = df[df["county_fips"].str.startswith(TARGET_STATE_FIPS)].copy()
        df[COL_SCORE] = pd.to_numeric(df[COL_SCORE], errors="coerce")
        return (df.groupby("county_fips")[COL_SCORE].mean().round().reset_index()
                  .rename(columns={COL_SCORE: "mental_health_hpsa_score"}))
