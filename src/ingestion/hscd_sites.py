"""HRSA Health Center Service Delivery + Look-Alike Sites -> real grantee-site glyphs.

Point-level (not county-keyed), so this doesn't subclass RealSource/BaseSource
(which assert a county_fips-keyed frame for the tall county_metric join) -- it's
consumed directly by src/build_sites.py instead.

Each row is one real, HRSA-funded health center site: name, parent organization,
address, site type, weekly operating hours, and lat/lon (HRSA calls it "Geocoding
Artifact Address Primary X/Y Coordinate"). No geocoding needed; HRSA ships it
pre-geocoded. This is the real replacement for the forest's invented "grantee"
names -- see dashboard/clinic-needs-forest.html's old buildDummyData().
"""

from __future__ import annotations

import pandas as pd
import requests

from src.catalog import REPO_ROOT

HSCD_SITES_CSV = ("https://data.hrsa.gov/DataDownload/DD_Files/"
                   "Health_Center_Service_Delivery_and_LookAlike_Sites.csv")
RAW_PATH = REPO_ROOT / "data" / "raw" / "hrsa_hscd_sites.csv"
TARGET_STATE_ABBR = "VA"


def fetch_raw(use_cache: bool = True) -> None:
    if use_cache and RAW_PATH.exists():
        return
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(HSCD_SITES_CSV, timeout=120,
                         headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    RAW_PATH.write_bytes(resp.content)


def extract() -> pd.DataFrame:
    df = pd.read_csv(RAW_PATH, low_memory=False)
    df = df[(df["Site State Abbreviation"] == TARGET_STATE_ABBR)
            & (df["Site Status Description"] == "Active")].copy()

    df["county_fips"] = (df["State and County Federal Information Processing Standard Code"]
                          .astype(str).str.strip().str.zfill(5))
    df["lat"] = pd.to_numeric(df["Geocoding Artifact Address Primary Y Coordinate"], errors="coerce")
    df["lon"] = pd.to_numeric(df["Geocoding Artifact Address Primary X Coordinate"], errors="coerce")
    df["operating_hours_per_week"] = pd.to_numeric(df["Operating Hours per Week"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"])

    out = pd.DataFrame({
        "kind": "grantee",
        "id": "hscd-" + df["BPHC Assigned Number"].astype(str),
        "name": df["Site Name"].astype(str).str.strip(),
        "org": df["Health Center Name"].astype(str).str.strip(),
        "siteType": df["Health Center Service Delivery Site Location Setting Description"].astype(str).str.strip(),
        "address": df["Site Address"].astype(str).str.strip(),
        "city": df["Site City"].astype(str).str.strip(),
        "county_fips": df["county_fips"],
        "lat": df["lat"].round(5),
        "lon": df["lon"].round(5),
        "operatingHoursPerWeek": df["operating_hours_per_week"],
        "ownerType": df["Grantee Organization Type Description"].astype(str).str.strip(),
    })
    return out.reset_index(drop=True)


def run(use_cache: bool = True) -> pd.DataFrame:
    fetch_raw(use_cache=use_cache)
    return extract()
