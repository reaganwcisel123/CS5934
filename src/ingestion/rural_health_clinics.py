"""Real Virginia Rural Health Clinic (RHC) point data -> rural-clinic glyphs.

Combines three free sources: CMS HCRIS RHC cost reports (identity + four real
per-clinic measures; worksheet codes verified against PRM-II Ch.46 Table 3,
r4p246i.pdf pp.55-68), HRSA Primary Care HPSA facility designations (shortage
score + lat/lon, reusing hrsa_hpsa.py's raw cache), and the Census Geocoder
with a ZCTA-centroid fallback. Point-level output (not county-keyed), consumed
by src/build_sites.py.
"""

from __future__ import annotations

import io
import re
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from src.catalog import REPO_ROOT
from src.ingestion.base import RAW_DIR, TARGET_STATE_FIPS

RAW_SUBDIR = RAW_DIR / "rhc"
HCRIS_REPORTS_ZIP = "https://downloads.cms.gov/Files/hcris/RHC17-REPORTS.zip"
HCRIS_DATA_ZIP = "https://downloads.cms.gov/Files/hcris/RHC17-ALL-YEARS.zip"
HPSA_RAW = RAW_DIR / "hrsa_hpsa.csv"  # cached by hrsa_hpsa.py; reused here as-is
GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
# ZCTA gazetteer: last-resort ZIP-centroid for addresses the geocoder can't resolve.
ZCTA_GAZETTEER_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_zcta_national.zip"
ZCTA_RAW = RAW_SUBDIR / "zcta_gaz.txt"

# (WKSHT_CD, LINE_NUM, CLMN_NUM) per PRM-II Ch.46 Table 3 (r4p246i.pdf
# pp.55-68); worksheet/line/column codes are not in the data files themselves.
COST_REPORT_CODES = {
    "physicianVisits": ("B000001", "00100", "00200"),      # Wksht B I, "Physicians" total visits
    "totalAdjustedVisits": ("C000001", "00600", "00100"),  # Wksht C I, all-provider visits
    "costPerVisit": ("C000001", "00700", "00100"),         # Wksht C I, adjusted cost per visit
    "totalAllowableCost": ("C000001", "00100", "00100"),   # Wksht C I, total allowable costs
}

RPT_COLS = ["RPT_REC_NUM", "PRVDR_CTRL_TYPE_CD", "PRVDR_NUM", "NPI", "RPT_STUS_CD",
            "FY_BGN_DT", "FY_END_DT", "PROC_DT", "INITL_RPT_SW", "LAST_RPT_SW",
            "TRNSMTL_NUM", "FI_NUM", "ADR_VNDR_CD", "FI_CREAT_DT", "UTIL_CD",
            "NPR_DT", "SPEC_IND", "FI_RCPT_DT"]
NMRC_COLS = ["RPT_REC_NUM", "WKSHT_CD", "LINE_NUM", "CLMN_NUM", "ITM_VAL_NUM"]

_UA = {"User-Agent": "Mozilla/5.0"}


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=120, headers=_UA)
    resp.raise_for_status()
    dest.write_bytes(resp.content)


def fetch_raw(use_cache: bool = True) -> None:
    RAW_SUBDIR.mkdir(parents=True, exist_ok=True)
    if not (use_cache and (RAW_SUBDIR / "hcris_reports.zip").exists()):
        _download(HCRIS_REPORTS_ZIP, RAW_SUBDIR / "hcris_reports.zip")
    if not (use_cache and (RAW_SUBDIR / "hcris_data.zip").exists()):
        _download(HCRIS_DATA_ZIP, RAW_SUBDIR / "hcris_data.zip")
    if not (use_cache and ZCTA_RAW.exists()):
        buf = io.BytesIO()
        resp = requests.get(ZCTA_GAZETTEER_URL, timeout=60, headers=_UA)
        resp.raise_for_status()
        buf.write(resp.content)
        with zipfile.ZipFile(buf) as z:
            name = next(n for n in z.namelist() if n.endswith(".txt"))
            ZCTA_RAW.write_bytes(z.read(name))


_ZCTA_CENTROIDS: dict[str, tuple[float, float]] | None = None


def _zcta_centroid(zip_code: str) -> tuple[float, float] | None:
    global _ZCTA_CENTROIDS
    if _ZCTA_CENTROIDS is None:
        gaz = pd.read_csv(ZCTA_RAW, sep="|", dtype={"GEOID": str})
        _ZCTA_CENTROIDS = {row.GEOID: (row.INTPTLAT, row.INTPTLONG) for row in gaz.itertuples()}
    zip5 = re.sub(r"\D", "", str(zip_code))[:5]
    return _ZCTA_CENTROIDS.get(zip5)


def _read_provider_id_info() -> pd.DataFrame:
    with zipfile.ZipFile(RAW_SUBDIR / "hcris_reports.zip") as z:
        with z.open("RHC17_PRVDR_ID_INFO.CSV") as f:
            return pd.read_csv(f, dtype=str)


def _read_hcris_table(kind: str, cols: list[str]) -> pd.DataFrame:
    """Concat every fiscal-year CSV of one table (rpt|nmrc) across the bulk zip."""
    frames = []
    with zipfile.ZipFile(RAW_SUBDIR / "hcris_data.zip") as z:
        names = [n for n in z.namelist() if n.endswith(f"_{kind}.csv")]
        for n in names:
            with z.open(n) as f:
                frames.append(pd.read_csv(f, header=None, names=cols, dtype=str))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)


def _cost_report_measures_by_provider() -> pd.DataFrame:
    """CCN -> most recent settled cost report's real measures (COST_REPORT_CODES)."""
    prov = _read_provider_id_info()
    va_ccns = set(prov.loc[prov["STATE"] == "VA", "PROVIDER_NUMBER"])

    rpt = _read_hcris_table("rpt", RPT_COLS)
    rpt_va = rpt[rpt["PRVDR_NUM"].isin(va_ccns)].copy()
    rpt_va["FY_END_DT"] = pd.to_datetime(rpt_va["FY_END_DT"], errors="coerce")
    latest = rpt_va.sort_values("FY_END_DT").groupby("PRVDR_NUM", as_index=False).tail(1)
    latest_rec_nums = set(latest["RPT_REC_NUM"])

    nmrc = _read_hcris_table("nmrc", NMRC_COLS)
    nmrc = nmrc[nmrc["RPT_REC_NUM"].isin(latest_rec_nums)]

    merged = latest.merge(prov, left_on="PRVDR_NUM", right_on="PROVIDER_NUMBER", how="left")
    for field, (wksht, line, clmn) in COST_REPORT_CODES.items():
        vals = nmrc[(nmrc["WKSHT_CD"] == wksht) & (nmrc["LINE_NUM"] == line) & (nmrc["CLMN_NUM"] == clmn)]
        vals = vals[["RPT_REC_NUM", "ITM_VAL_NUM"]].rename(columns={"ITM_VAL_NUM": field})
        merged = merged.merge(vals, on="RPT_REC_NUM", how="left")
        merged[field] = pd.to_numeric(merged[field], errors="coerce")

    merged["FY_END_DT"] = merged["FY_END_DT"].dt.strftime("%Y-%m-%d")
    return merged[["PRVDR_NUM", "RHC17_NAME", "STREET_ADDR", "CITY", "STATE", "ZIP_CODE",
                    "COUNTY", "FY_END_DT", *COST_REPORT_CODES]]


def _normalize_name(s: str) -> str:
    s = re.sub(r"[^A-Z0-9 ]", " ", str(s).upper())
    return re.sub(r"\s+", " ", s).strip()


# Corporate suffixes that differ between HCRIS and HPSA for the same facility;
# stripped iteratively so multi-token suffixes ("INC ASSOCIATES") fully resolve.
_CORP_SUFFIX_RE = re.compile(r"\s+(INC|CORP|CORPORATION|LLC|PLLC|P ?C|ASSOCIATES|ASSOC|GROUP)\.?$")
# HPSA sometimes appends "- CITY"; only a short trailing "- WORD [WORD]" tail
# is stripped so this can't over-match.
_TRAILING_QUALIFIER_RE = re.compile(r"\s*-\s*[A-Z]+(\s+[A-Z]+)?$")


def _strip_corp_suffix(name_key: str) -> str:
    s = _TRAILING_QUALIFIER_RE.sub("", name_key)
    prev = None
    while prev != s:
        prev = s
        s = _CORP_SUFFIX_RE.sub("", s)
    return s.strip()


def _hpsa_rhc_rows() -> pd.DataFrame:
    """Facility-level HPSA rows for VA where Designation Type == Rural Health Clinic."""
    df = pd.read_csv(HPSA_RAW, low_memory=False)
    df = df[(df["Primary State Abbreviation"] == "VA")
            & (df["Designation Type"] == "Rural Health Clinic")].copy()
    df["_name_key"] = df["HPSA Name"].map(_normalize_name)
    df["_stripped_key"] = df["_name_key"].map(_strip_corp_suffix)
    df["_county_key"] = df["Common County Name"].map(_strip_county_suffix)
    df["_update_dt"] = pd.to_datetime(df["HPSA Designation Last Update Date"], errors="coerce")
    return df[["_name_key", "_stripped_key", "_county_key", "HPSA Score", "Longitude", "Latitude",
               "HPSA Status", "HPSA FTE", "_update_dt", "Common County Name"]]


def _haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in meters."""
    r = 6371000
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dl = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


# Two independently-sourced points this close is treated as the same building.
# Kept tight so "two clinics on the same block" never counts as a match.
PROXIMITY_MATCH_METERS = 75


def _match_hpsa(name_key: str, county_raw: str | None, hpsa: pd.DataFrame) -> tuple[dict | None, object]:
    """Match one HCRIS clinic to an HPSA row: exact name, then suffix-stripped
    name, then narrowed by county; same-county leftovers prefer the Designated
    or most recently updated row. Ambiguous cross-county names stay unmatched
    (the caller geocodes) rather than risking a wrong coordinate."""
    candidates = hpsa[hpsa["_name_key"] == name_key]
    if candidates.empty:
        candidates = hpsa[hpsa["_stripped_key"] == _strip_corp_suffix(name_key)]
    if candidates.empty:
        return None, None
    if len(candidates) == 1:
        return candidates.iloc[0].to_dict(), candidates.index[0]

    if county_raw:
        county_key = _strip_county_suffix(county_raw)
        by_county = candidates[candidates["_county_key"] == county_key]
        if len(by_county) == 1:
            return by_county.iloc[0].to_dict(), by_county.index[0]
        if len(by_county) > 1:
            candidates = by_county  # narrowed, but still ambiguous -> fall through

    if candidates["_county_key"].nunique() == 1:
        # Same facility, different designation vintages -- prefer the
        # current designation, else the most recently updated record.
        designated = candidates[candidates["HPSA Status"] == "Designated"]
        pool = designated if not designated.empty else candidates
        picked = pool.sort_values("_update_dt").iloc[[-1]]
        return picked.iloc[0].to_dict(), picked.index[0]

    return None, None  # genuinely different facilities sharing a name; no safe pick


def _nearest_hpsa_within(lat: float, lon: float, hpsa: pd.DataFrame, exclude_idx: set,
                          max_m: float = PROXIMITY_MATCH_METERS) -> tuple[dict | None, object]:
    """Match by proximity: an unclaimed HPSA point within max_m of the clinic's
    independently street-geocoded position counts as the same facility."""
    pool = hpsa.drop(index=[i for i in exclude_idx if i in hpsa.index])
    pool = pool.dropna(subset=["Latitude", "Longitude"])
    if pool.empty:
        return None, None
    d = _haversine_m(lat, lon, pool["Latitude"].values, pool["Longitude"].values)
    i = d.argmin()
    if d[i] <= max_m:
        idx = pool.index[i]
        return pool.iloc[i].to_dict(), idx
    return None, None


def _geocode(address: str, city: str, zip_code: str) -> dict | None:
    """Census Geocoder -> {lat, lon, county_fips, precision} or None. Falls back
    street -> street w/o suite -> city+zip centroid; `precision` records which."""
    stripped = re.sub(r"\s+(STE|SUITE|UNIT|#)\s*\S*$", "", address, flags=re.I).strip()
    candidates = [(f"{address}, {city}, VA {zip_code}", "address")]
    if stripped != address:
        candidates.append((f"{stripped}, {city}, VA {zip_code}", "address"))
    candidates.append((f"{city}, VA {zip_code}", "city_centroid"))

    for addr, precision in candidates:
        try:
            resp = requests.get(GEOCODER_URL, timeout=20, params={
                "address": addr, "benchmark": "Public_AR_Current",
                "vintage": "Current_Current", "layers": "Counties", "format": "json",
            })
            resp.raise_for_status()
            matches = resp.json()["result"]["addressMatches"]
        except (requests.RequestException, KeyError, ValueError):
            continue
        if matches:
            m = matches[0]
            counties = m["geographies"].get("Counties", [])
            return {
                "lat": round(m["coordinates"]["y"], 5),
                "lon": round(m["coordinates"]["x"], 5),
                "county_fips": counties[0]["GEOID"] if counties else None,
                "precision": precision,
            }
        time.sleep(0.2)
    return None


def _strip_county_suffix(s: str) -> str:
    # HPSA county names carry a trailing ", VA" that va_county_region.csv's don't.
    s = re.sub(r"\s+VA$", "", _normalize_name(s))
    return re.sub(r"\s+(COUNTY|CITY)$", "", s).strip()


def _county_fips_by_name() -> dict[str, str]:
    """Key on the bare county name: HCRIS and va_county_region.csv disagree on
    the County/city suffix, so it is stripped from both sides."""
    ref = pd.read_csv(REPO_ROOT / "data" / "reference" / "va_county_region.csv", dtype=str)
    return {_strip_county_suffix(n): fips for n, fips in zip(ref["county_name"], ref["county_fips"])}


def extract(geocode_missing: bool = True) -> pd.DataFrame:
    clinics = _cost_report_measures_by_provider()
    hpsa = _hpsa_rhc_rows()
    fips_by_name = _county_fips_by_name()

    rows = []
    claimed_hpsa_idx: set = set()
    for _, r in clinics.iterrows():
        name_key = _normalize_name(r["RHC17_NAME"])
        county_raw = r["COUNTY"] if pd.notna(r.get("COUNTY")) else None
        match, match_idx = _match_hpsa(name_key, county_raw, hpsa)

        lat, lon, county_fips, geo_source = None, None, None, None
        hpsa_score = hpsa_status = None
        if match and pd.notna(match.get("Latitude")) and pd.notna(match.get("Longitude")):
            lat, lon = round(float(match["Latitude"]), 5), round(float(match["Longitude"]), 5)
            geo_source = "hpsa"
            hpsa_score = int(float(match["HPSA Score"])) if pd.notna(match.get("HPSA Score")) else None
            hpsa_status = match.get("HPSA Status")
            claimed_hpsa_idx.add(match_idx)
        elif geocode_missing:
            g = _geocode(r["STREET_ADDR"], r["CITY"], r["ZIP_CODE"])
            if g:
                lat, lon, county_fips = g["lat"], g["lon"], g["county_fips"]
                geo_source = "geocoded" if g["precision"] == "address" else "geocoded_city_centroid"
            else:
                zc = _zcta_centroid(r["ZIP_CODE"])
                if zc:
                    lat, lon = zc
                    geo_source = "zip_centroid"

        if not county_fips and county_raw:
            county_fips = fips_by_name.get(_strip_county_suffix(county_raw))
        if not county_fips and match is not None and pd.notna(match.get("Common County Name")):
            # HCRIS's COUNTY is blank for some independent cities; use the matched HPSA row's.
            county_fips = fips_by_name.get(_strip_county_suffix(match["Common County Name"]))

        cost_report_asof = r.get("FY_END_DT") if pd.notna(r.get("FY_END_DT")) else None
        rows.append({
            "kind": "rural_clinic",
            "id": f"ccn-{r['PRVDR_NUM']}",
            "name": str(r["RHC17_NAME"]).strip(),
            "address": str(r["STREET_ADDR"]).strip(),
            "city": str(r["CITY"]).strip(),
            "county_fips": county_fips,
            "countyNameRaw": county_raw,
            "lat": lat, "lon": lon,
            "geoSource": geo_source,
            "hpsaScore": hpsa_score,
            "hpsaStatus": hpsa_status,
            "physicianVisits": (int(r["physicianVisits"]) if pd.notna(r.get("physicianVisits")) else None),
            "totalAdjustedVisits": (int(r["totalAdjustedVisits"]) if pd.notna(r.get("totalAdjustedVisits")) else None),
            "costPerVisit": (round(float(r["costPerVisit"]), 2) if pd.notna(r.get("costPerVisit")) else None),
            "totalAllowableCost": (int(r["totalAllowableCost"]) if pd.notna(r.get("totalAllowableCost")) else None),
            "costReportAsOf": cost_report_asof,
        })

    # Second pass: proximity-match clinics the name match couldn't resolve.
    # Only for geoSource == "geocoded" so the distance comparison is trustworthy.
    for row in rows:
        if row["hpsaScore"] is not None or row["geoSource"] != "geocoded":
            continue
        match, match_idx = _nearest_hpsa_within(row["lat"], row["lon"], hpsa, claimed_hpsa_idx)
        if match:
            row["hpsaScore"] = int(float(match["HPSA Score"])) if pd.notna(match.get("HPSA Score")) else None
            row["hpsaStatus"] = match.get("HPSA Status")
            row["geoSource"] = "hpsa_proximity"
            claimed_hpsa_idx.add(match_idx)

    return pd.DataFrame(rows)


def run(use_cache: bool = True, geocode_missing: bool = True) -> pd.DataFrame:
    fetch_raw(use_cache=use_cache)
    return extract(geocode_missing=geocode_missing)
