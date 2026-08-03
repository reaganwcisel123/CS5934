"""CDC PLACES county health outcomes -> dashboard outcomes.* (Socrata, no auth)."""

from __future__ import annotations

import pandas as pd
import requests

from src.ingestion.base import RealSource, TARGET_STATE_FIPS

# PLACES MeasureId -> dashboard outcome key.
MEASURE_MAP = {"DIABETES": "diabetes", "OBESITY": "obesity",
               "MHLTH": "mhlth", "BPHIGH": "bphigh",
               "DEPRESSION": "depression", "CSMOKING": "smoking"}
STATE_ABBR = "VA"


def _socrata_id(access_url: str) -> str:
    # Dataset id (e.g. "swc5-untb") is the last path segment of the catalog URL.
    return access_url.rstrip("/").split("/")[-1]


class CdcPlaces(RealSource):
    source_id = "cdc_places"

    def fetch_raw(self) -> None:
        endpoint = f"https://data.cdc.gov/resource/{_socrata_id(self.access_url)}.csv"
        measures = "','".join(MEASURE_MAP)
        params = {
            "$select": "locationid,measureid,data_value,data_value_type",
            "$where": (f"stateabbr='{STATE_ABBR}' and measureid in('{measures}') "
                       "and data_value_type='Age-adjusted prevalence'"),
            "$limit": "50000",
        }
        resp = requests.get(endpoint, params=params, timeout=60)
        resp.raise_for_status()
        self.raw_path.write_bytes(resp.content)

    def extract(self) -> pd.DataFrame:
        # Pivot long measure rows into one column per outcome, keyed by county.
        df = pd.read_csv(self.raw_path, dtype={"locationid": str})
        df = df[df["measureid"].isin(MEASURE_MAP)]
        wide = (df.pivot_table(index="locationid", columns="measureid", values="data_value")
                  .rename(columns=MEASURE_MAP).reset_index()
                  .rename(columns={"locationid": "county_fips"}))
        wide["county_fips"] = wide["county_fips"].str.zfill(5)
        return wide[wide["county_fips"].str.startswith(TARGET_STATE_FIPS)]
