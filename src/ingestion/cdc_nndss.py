"""CDC NNDSS weekly notifiable-disease surveillance -> Virginia condition time series.

NNDSS is state-keyed, not county-keyed (see the catalog entry's granularity and
limitations), so this returns one row per (condition, mmwr_year, mmwr_week) and
overrides run() to skip BaseSource's county_fips assertion. The county bridge is
downstream in src/model/forecast_dataset.py, which allocates and says so.

Run standalone:
    uv run python -m src.ingestion.cdc_nndss
"""

from __future__ import annotations

import sys

import pandas as pd
import requests

from src.catalog import REPO_ROOT
from src.ingestion.base import RealSource, Provenance

TARGET_JURISDICTION = "VIRGINIA"

# Neighbours are pulled so threat ranking can corroborate a Virginia rise against
# the region (US-056). Anything modelling Virginia must filter to
# TARGET_JURISDICTION -- this frame is no longer one row per condition-week.
NEIGHBOR_JURISDICTIONS = [
    "MARYLAND", "WEST VIRGINIA", "KENTUCKY",
    "TENNESSEE", "NORTH CAROLINA", "DISTRICT OF COLUMBIA",
]
REGION_JURISDICTIONS = [TARGET_JURISDICTION, *NEIGHBOR_JURISDICTIONS]

# CDC writes "VIRGINIA" for 2022-2024 and "Virginia" from 2025 on, so an
# equality filter silently drops the two most recent years.
_STATE_PREDICATE = "upper(states) in ({jurisdictions})"

# m1 is the current-week count. m2 (cumulative YTD) is skipped: it resets each
# MMWR year and would put a sawtooth into every lag feature.
COLUMN_MAP = {"year": "mmwr_year", "week": "mmwr_week", "label": "condition", "m1": "cases"}

NO_FLAG = "-"
OUT_PATH = REPO_ROOT / "data" / "processed" / "region_condition_history.csv"


def _state_predicate(jurisdictions: list[str] = None) -> str:
    names = jurisdictions or REGION_JURISDICTIONS
    return _STATE_PREDICATE.format(jurisdictions=",".join(f"'{n}'" for n in names))


def _socrata_id(access_url: str) -> str:
    return access_url.rstrip("/").split("/")[-1]


class CdcNndss(RealSource):
    source_id = "cdc_nndss"
    provenance = Provenance.REAL

    def fetch_raw(self) -> None:
        endpoint = f"https://data.cdc.gov/resource/{_socrata_id(self.access_url)}.csv"
        params = {
            "$select": "year,week,label,m1,m1_flag,states",
            "$where": _state_predicate(),
            "$limit": "400000",
        }
        resp = requests.get(endpoint, params=params, timeout=180)
        resp.raise_for_status()
        self.raw_path.write_bytes(resp.content)

    def extract(self) -> pd.DataFrame:
        return self._clean(pd.read_csv(self.raw_path))

    @staticmethod
    def _clean(df: pd.DataFrame) -> pd.DataFrame:
        # staticmethod so tests can drive the rules from a fixture frame.
        out = df.rename(columns=COLUMN_MAP).copy()

        for required in ("mmwr_year", "mmwr_week", "condition"):
            if required not in out.columns:
                raise ValueError(f"cdc_nndss: missing required column '{required}'")

        out["mmwr_year"] = pd.to_numeric(out["mmwr_year"], errors="coerce").astype("Int64")
        out["mmwr_week"] = pd.to_numeric(out["mmwr_week"], errors="coerce").astype("Int64")
        out["cases"] = pd.to_numeric(out.get("cases"), errors="coerce")
        out["condition"] = out["condition"].astype(str).str.strip()

        # Upper-cased so the 2022-2024 / 2025+ casing split collapses to one key.
        out["jurisdiction"] = (out["states"].astype(str).str.strip().str.upper()
                               if "states" in out.columns else TARGET_JURISDICTION)

        # A flagged row (N/U/NC) is unreported, not zero cases.
        if "m1_flag" in out.columns:
            flagged = out["m1_flag"].notna() & (out["m1_flag"].astype(str).str.strip() != NO_FLAG)
            out.loc[flagged, "cases"] = pd.NA

        out = out.dropna(subset=["mmwr_year", "mmwr_week", "condition"])
        out = out[out["condition"] != ""]

        # Provisional weeks get reissued; the latest revision wins.
        key = ["jurisdiction", "condition", "mmwr_year", "mmwr_week"]
        out = (out.sort_values(key)
                  .drop_duplicates(subset=key, keep="last")
                  .reset_index(drop=True))

        return out[["jurisdiction", "condition", "mmwr_year", "mmwr_week", "cases"]]

    def run(self, use_cache: bool = True) -> pd.DataFrame:
        if not (use_cache and self.raw_path.exists()):
            self.raw_path.parent.mkdir(parents=True, exist_ok=True)
            self.fetch_raw()
        df = self.extract()
        _assert_condition_week_keyed(df)
        return df


def _assert_condition_week_keyed(df: pd.DataFrame) -> None:
    """State-level analogue of BaseSource's county_fips check."""
    required = {"jurisdiction", "condition", "mmwr_year", "mmwr_week"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"cdc_nndss: extract() must return {sorted(required)}; missing {sorted(missing)}")
    if df.duplicated(subset=sorted(required)).any():
        raise ValueError(
            "cdc_nndss: duplicate (jurisdiction, condition, mmwr_year, mmwr_week) rows survived cleaning"
        )


def main() -> int:
    from src.catalog import Catalog

    df = CdcNndss(Catalog.load()).run(use_cache="--refresh" not in sys.argv)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    reported = int(df["cases"].notna().sum())
    print(f"Wrote {OUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  {len(df)} rows | {df['jurisdiction'].nunique()} jurisdictions | "
          f"{df['condition'].nunique()} conditions | "
          f"{df.groupby(['mmwr_year', 'mmwr_week']).ngroups} weeks")
    print(f"  {reported} reported, {len(df) - reported} suppressed (kept NULL)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
