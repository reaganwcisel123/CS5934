"""USDA Food Access Atlas -> food-burden domain (county LI/LA share)."""

from __future__ import annotations

import pandas as pd
import requests

from src.ingestion.base import RealSource, TARGET_STATE_FIPS

ATLAS_XLSX = ("https://ers.usda.gov/sites/default/files/_laserfiche/DataFiles/80591/"
              "FoodAccessResearchAtlasData2019.xlsx")
SHEET = "Food Access Research Atlas"
TRACT_COL, LILA_COL = "CensusTract", "LILATracts_1And10"


class UsdaFoodAccess(RealSource):
    source_id = "usda_food_access"

    @property
    def raw_path(self):
        return super().raw_path.with_suffix(".xlsx")  # caches an xlsx, not csv

    def fetch_raw(self) -> None:
        resp = requests.get(ATLAS_XLSX, timeout=180)
        resp.raise_for_status()
        self.raw_path.write_bytes(resp.content)

    def extract(self) -> pd.DataFrame:
        # Aggregate tract LILA flags to a county share (0-100%).
        df = pd.read_excel(self.raw_path, sheet_name=SHEET, dtype={TRACT_COL: str})
        df["county_fips"] = df[TRACT_COL].str.zfill(11).str[:5]
        df = df[df["county_fips"].str.startswith(TARGET_STATE_FIPS)]
        df[LILA_COL] = pd.to_numeric(df[LILA_COL], errors="coerce")
        return (df.groupby("county_fips")[LILA_COL].mean().mul(100).round(1).reset_index()
                  .rename(columns={LILA_COL: "low_income_low_access_share"}))
