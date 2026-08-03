"""Real Virginia Rural Health Clinic (RHC) point data -> rural-clinic glyphs.

RHCs are a separate CMS reimbursement designation from HRSA Health Center
Program grantees (see hscd_sites.py) and are NOT required to report HRSA's
UDS clinical quality measures, so there is no RHC equivalent of htn_control /
dm_poor / etc. What IS real and freely available, combined here:

  1. CMS HCRIS RHC Cost Report (Form CMS-222-17) -- both identity (name,
     street address, city, county -- from its own RHC17_PRVDR_ID_INFO.CSV,
     which made a separate PECOS Enrollments fetch unnecessary) and four real
     per-clinic numbers from the clinic's most recent settled cost report:
     physician visits, total adjusted visits (all provider types), adjusted
     cost per visit, and total allowable cost. Worksheet/line/column codes
     for RHC17 aren't in the data files themselves -- they're defined in the
     Provider Reimbursement Manual Part II Chapter 46 "Table 3 - List of Data
     Elements with Worksheet, Line, and Column Designations"
     (https://www.cms.gov/files/document/r4p246i.pdf, pages 55-68), which is
     where every *_CODE constant below comes from. Nothing here is guessed --
     each code was verified against that table, then spot-checked against the
     actual VA cost report data before being wired in.
     https://www.cms.gov/data-research/statistics-trends-and-reports/cost-reports/rural-health-center-222-2017-form
  2. HRSA Primary Care HPSA facility designations, Designation Type == "Rural
     Health Clinic" -- real per-facility shortage severity (HPSA Score) with
     real lat/lon already attached. Reuses the raw cache hrsa_hpsa.py already
     fetches (data/raw/hrsa_hpsa.csv), no extra fetch needed. Matched two
     ways: (a) by name (after stripping corporate suffixes and city
     qualifiers -- see _strip_corp_suffix) plus county/status disambiguation
     when a name maps to more than one HPSA row -- see _match_hpsa's
     docstring; (b) for clinics that don't resolve by name (HPSA often labels
     multi-site systems generically, e.g. "CARILION CLINIC" for five
     different VA facilities), by proximity -- if the clinic's independently
     street-geocoded position lands within PROXIMITY_MATCH_METERS of an
     unclaimed HPSA point, that's treated as strong enough evidence of the
     same building. See _nearest_hpsa_within.
  3. Census Geocoder (geocoding.geo.census.gov, free/keyless) fills in
     lat/lon + county_fips for clinics the HPSA file doesn't cover, with a
     Census ZCTA gazetteer centroid as a last-resort fallback for addresses
     it can't resolve at all.

Point-level output (not county-keyed), consumed by src/build_sites.py.
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
# Census ZCTA gazetteer: last-resort centroid for addresses the point geocoder
# can't resolve at all (common for rural highway addresses with no TIGER
# address range). Real Census geography, just ZIP-centroid precision rather
# than a street point.
ZCTA_GAZETTEER_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_zcta_national.zip"
ZCTA_RAW = RAW_SUBDIR / "zcta_gaz.txt"

# Verified against PRM-II Ch.46 "Table 3 - List of Data Elements with
# Worksheet, Line, and Column Designations" (r4p246i.pdf pp.55-68), then
# spot-checked against the actual VA data. Each tuple is (WKSHT_CD, LINE_NUM,
# CLMN_NUM) in the electronic-cost-report encoding (line/column N -> "NNN00").
COST_REPORT_CODES = {
    # Worksheet B, Part I, Line 1 ("Physicians"), Col 2 ("Total Visits") --
    # also CMS's own worked example in RHC17_README.txt.
    "physicianVisits": ("B000001", "00100", "00200"),
    # Worksheet C, Part I, Line 6, Col 1: "Total adjusted visits" (all
    # provider types, the rate-setting visit count -- a fuller utilization
    # figure than physician visits alone).
    "totalAdjustedVisits": ("C000001", "00600", "00100"),
    # Worksheet C, Part I, Line 7, Col 1: "Adjusted cost per visit" -- a
    # scale-normalized efficiency figure, comparable across clinics of very
    # different sizes (unlike raw visit counts or raw total cost).
    "costPerVisit": ("C000001", "00700", "00100"),
    # Worksheet C, Part I, Line 1, Col 1: "Total allowable costs" -- the
    # facility's real bottom-line annual operating cost for the cost report
    # period.
    "totalAllowableCost": ("C000001", "00100", "00100"),
}

RPT_COLS = ["RPT_REC_NUM", "PRVDR_CTRL_TYPE_CD", "PRVDR_NUM", "NPI", "RPT_STUS_CD",
            "FY_BGN_DT", "FY_END_DT", "PROC_DT", "INITL_RPT_SW", "LAST_RPT_SW",
            "TRNSMTL_NUM", "FI_NUM", "ADR_VNDR_CD", "FI_CREAT_DT", "UTIL_CD",
            "NPR_DT", "SPEC_IND", "FI_RCPT_DT"]
NMRC_COLS = ["RPT_REC_NUM", "WKSHT_CD", "LINE_NUM", "CLMN_NUM", "ITM_VAL_NUM"]

_UA = {"User-Agent": "Mozilla/5.0"}


def _download(url: str, dest: Path) -> None:
    if dest.exists():
        return
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


# Corporate suffixes that differ between the two source systems for the same
# real facility (e.g. HCRIS "CLINCH VALLEY PHYSICIANS ASSOCIATES" vs HPSA
# "CLINCH VALLEY PHYSICIANS"). Stripped iteratively so multi-token suffixes
# ("INC ASSOCIATES") still fully resolve.
_CORP_SUFFIX_RE = re.compile(r"\s+(INC|CORP|CORPORATION|LLC|PLLC|P ?C|ASSOCIATES|ASSOC|GROUP)\.?$")
# HPSA names sometimes append a location qualifier HCRIS doesn't use, e.g.
# "MERIT MEDICAL RURAL HEALTH CLINIC - RICHLANDS" / "PATRICK COUNTY FAMILY
# PRACTICE - STUART". Only strips a short trailing "- WORD" or "- WORD WORD"
# tail, not arbitrary text, to keep this from over-matching.
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
    """Great-circle distance in meters -- used to cross-check name matches
    against real independently-collected coordinates."""
    r = 6371000
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dl = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


# Two independently-sourced points (HCRIS street-geocoded address vs. HRSA's
# HPSA facility record) landing this close together is strong evidence of the
# same real building, regardless of whether the names matched -- rescues
# facilities HPSA labels generically (e.g. "CARILION CLINIC") that a
# name-based match can't safely disambiguate on its own. Kept tight (a
# building + parking lot footprint) specifically so it doesn't paper over
# "two different clinics on the same block" as a match.
PROXIMITY_MATCH_METERS = 75


def _match_hpsa(name_key: str, county_raw: str | None, hpsa: pd.DataFrame) -> tuple[dict | None, object]:
    """Multiple VA facilities can share a name (e.g. several "CARILION CLINIC"
    HPSA rows in different counties) -- and the same facility is sometimes
    named slightly differently between HCRIS and HPSA (a corporate suffix
    like "ASSOCIATES", or HPSA appending "- CITY"). Strategy, most to least
    strict:
      1. Exact name match.
      2. Match after stripping corporate suffixes / trailing "- CITY" from
         both sides (rescues real near-duplicates like "CLINCH VALLEY
         PHYSICIANS" vs "...PHYSICIANS ASSOCIATES").
      3. If either step finds >1 candidate: narrow by county if HCRIS's
         COUNTY field is populated; if that still leaves >1 but they're all
         the *same* county (e.g. a Designated row and a stale Withdrawn row
         for one facility, re-designated over time), prefer HPSA Status ==
         "Designated", else the most recently updated row.
    Genuinely different facilities sharing a generic name across different
    counties (several "CARILION CLINIC" HPSA rows, no HCRIS county to
    disambiguate) are left unmatched rather than guessed -- the caller falls
    back to geocoding instead of risking a wrong coordinate."""
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
    """Fallback for clinics a name match couldn't resolve: if the clinic's
    independently street-geocoded position lands within max_m of an
    un-claimed HPSA facility point, treat that as a match. Two unrelated
    government sources agreeing on a location this precisely is stronger
    evidence than the facility names agreeing."""
    pool = hpsa.drop(index=[i for i in exclude_idx if i in hpsa.index])
    if pool.empty:
        return None, None
    d = _haversine_m(lat, lon, pool["Latitude"].values, pool["Longitude"].values)
    i = d.argmin()
    if d[i] <= max_m:
        idx = pool.index[i]
        return pool.iloc[i].to_dict(), idx
    return None, None


def _geocode(address: str, city: str, zip_code: str) -> dict | None:
    """Census Geocoder (free, keyless); returns {lat, lon, county_fips, precision}
    or None. Tries progressively coarser forms of the address: Census's TIGER
    address ranges frequently don't resolve rural highway addresses, especially
    with a suite/unit attached, so this falls back street -> street w/o suite
    -> city+zip centroid (still real geography, just less precise -- flagged
    via `precision` so the caller/UI can be honest about it)."""
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
    # HPSA's "Common County Name" carries a trailing state abbreviation
    # ("James City County, VA") that va_county_region.csv's names don't.
    s = re.sub(r"\s+VA$", "", _normalize_name(s))
    return re.sub(r"\s+(COUNTY|CITY)$", "", s).strip()


def _county_fips_by_name() -> dict[str, str]:
    """HCRIS's COUNTY field ('TAZEWELL', 'GALAX CITY') doesn't consistently
    carry the County/city suffix va_county_region.csv uses ('Tazewell County',
    'Galax city'), so key on the bare name with the suffix stripped from both
    sides."""
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
            hpsa_score = int(match["HPSA Score"]) if pd.notna(match.get("HPSA Score")) else None
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
            # HCRIS's own COUNTY field is blank for some independent-city
            # clinics (e.g. Williamsburg); fall back to the matched HPSA
            # row's county, which is real and already known-correct here.
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

    # Second pass: rescue clinics a name match couldn't resolve (e.g. HPSA's
    # generic "CARILION CLINIC" rows) by checking whether the clinic's real
    # street-geocoded position lands within PROXIMITY_MATCH_METERS of an
    # unclaimed HPSA point. Only applied to geoSource == "geocoded" (a real
    # address match, not a city/ZIP-centroid approximation) so the distance
    # comparison itself is trustworthy.
    for row in rows:
        if row["hpsaScore"] is not None or row["geoSource"] != "geocoded":
            continue
        match, match_idx = _nearest_hpsa_within(row["lat"], row["lon"], hpsa, claimed_hpsa_idx)
        if match:
            row["hpsaScore"] = int(match["HPSA Score"]) if pd.notna(match.get("HPSA Score")) else None
            row["hpsaStatus"] = match.get("HPSA Status")
            row["geoSource"] = "hpsa_proximity"
            claimed_hpsa_idx.add(match_idx)

    return pd.DataFrame(rows)


def run(use_cache: bool = True, geocode_missing: bool = True) -> pd.DataFrame:
    fetch_raw(use_cache=use_cache)
    return extract(geocode_missing=geocode_missing)
