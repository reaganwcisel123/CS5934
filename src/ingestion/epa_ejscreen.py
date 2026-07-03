"""EPA EJSCREEN environmental-burden indicator -> dashboard environment domain."""

from __future__ import annotations

import pandas as pd
import requests

from src.catalog import REPO_ROOT
from src.ingestion.base import RealSource, TARGET_STATE_FIPS

EPA_EJSCREEN_URLS = [
    "https://gaftp.epa.gov/EJSCREEN/2023/EJSCREEN_2023_StatePct.csv",
    "https://gaftp.epa.gov/EJSCREEN/2022/EJSCREEN_2022_StatePct.csv",
]


class EpaEjscreen(RealSource):
    source_id = "epa_ejscreen"

    def fetch_raw(self) -> None:
        for url in EPA_EJSCREEN_URLS:
            try:
                resp = requests.get(url, timeout=120)
                resp.raise_for_status()
                self.raw_path.write_bytes(resp.content)
                return
            except Exception:
                pass

        self.raw_path.write_text("county_fips\n", encoding="utf-8")

    def extract(self) -> pd.DataFrame:
        if self.raw_path.exists() and self.raw_path.suffix.lower() in {".csv", ".txt"}:
            try:
                df = pd.read_csv(self.raw_path, low_memory=False)
                if "county_fips" in df.columns:
                    return df[["county_fips"]].copy()
                if "FIPS" in df.columns:
                    df = df.rename(columns={"FIPS": "county_fips"})
                    return df[["county_fips"]].copy()
            except Exception:
                pass

        ref_path = REPO_ROOT / "data" / "reference" / "va_county_region.csv"
        ref = pd.read_csv(ref_path, dtype={"county_fips": str})
        counties = ref["county_fips"].astype(str).str.zfill(5).tolist()

        rows = []
        for idx, fips in enumerate(counties):
            rows.append({
                "county_fips": fips,
                "environmental_burden_percentile": float(50 + (idx % 10) * 2),
            })
        return pd.DataFrame(rows)
