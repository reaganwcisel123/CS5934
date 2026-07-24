"""CDC/ATSDR Environmental Justice Index -> dashboard environment domain (US-009).

The environment domain is the Environmental Burden Module percentile (RPL_EBM)
from the CDC/ATSDR Environmental Justice Index 2024. The national file is at the
census-tract level, so the tract RPL_EBM is population-weighted up to the county
and scaled to 0-100. The resulting county values for Virginia are committed in
data/reference/va_county_environment.csv, so the build reproduces offline. This
replaces the retired EPA EJSCREEN source, whose download host was deprecated.
"""

from __future__ import annotations

import pandas as pd

from src.catalog import REPO_ROOT
from src.ingestion.base import RealSource, TARGET_STATE_FIPS

# Committed county-level burden derived from the national EJI 2024 tract file.
ENVIRONMENT_REF = REPO_ROOT / "data" / "reference" / "va_county_environment.csv"


class CdcEji(RealSource):
    source_id = "cdc_eji"

    def fetch_raw(self) -> None:
        # County burden is a committed reference table, so no network fetch is
        # needed; copy it into the raw cache to satisfy the base contract.
        self.raw_path.write_text(ENVIRONMENT_REF.read_text(encoding="utf-8"), encoding="utf-8")

    def extract(self) -> pd.DataFrame:
        # Read the committed county-level environmental burden percentiles.
        df = pd.read_csv(ENVIRONMENT_REF, dtype={"county_fips": str})
        df["county_fips"] = df["county_fips"].str.zfill(5)
        # Keep only the target state's counties.
        df = df[df["county_fips"].str.startswith(TARGET_STATE_FIPS)]
        return df[["county_fips", "environmental_burden_percentile"]].reset_index(drop=True)
