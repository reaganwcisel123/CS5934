"""Build the point-level dataset behind the glyph forest's site glyphs.

clinic_atlas.json (src/build_dataset.py) is county-shaped: one record per
county. The forest's glyphs are per-site, so this is a separate small
pipeline that writes dashboard/data/clinic_sites.json:

    hscd_sites.py         -> 238 real HRSA-funded grantee sites (VA)
    rural_health_clinics.py -> 40 real Rural Health Clinics (VA)
    cdc_places.py          -> real county PLACES burden, attached to every
                               site by its county_fips (no facility-level
                               PLACES equivalent exists, so this is an
                               explicit county-context field, not a per-site
                               measurement -- see "countyBurden" below)

Run:
    python src/build_sites.py            # use cached raw extracts
    python src/build_sites.py --refresh   # re-fetch + re-geocode
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.catalog import Catalog, REPO_ROOT
from src.ingestion import hscd_sites, rural_health_clinics
from src.ingestion.cdc_places import CdcPlaces

OUT_PATH = REPO_ROOT / "dashboard" / "data" / "clinic_sites.json"
BURDEN_FIELDS = ["bphigh", "diabetes", "depression", "smoking"]


def build(refresh: bool = False) -> dict:
    catalog = Catalog.load()
    use_cache = not refresh

    print("Fetching real grantee sites (HRSA HSCD)...")
    grantees = hscd_sites.run(use_cache=use_cache)

    print("Fetching real rural health clinics (CMS HCRIS + HRSA HPSA + Census geocoder)...")
    rural = rural_health_clinics.run(use_cache=use_cache, geocode_missing=True)

    print("Fetching real county PLACES burden (for county-context sizing)...")
    places = CdcPlaces(catalog).run(use_cache=use_cache).set_index("county_fips")

    def county_burden(fips: str | None) -> dict | None:
        if not fips or fips not in places.index:
            return None
        row = places.loc[fips]
        return {f: (None if pd.isna(row[f]) else round(float(row[f]), 1)) for f in BURDEN_FIELDS}

    sites = []
    for _, r in grantees.iterrows():
        d = r.to_dict()
        d["countyBurden"] = county_burden(d.get("county_fips"))
        sites.append(_clean(d))
    for _, r in rural.iterrows():
        d = r.to_dict()
        d["countyBurden"] = county_burden(d.get("county_fips"))
        sites.append(_clean(d))

    return {
        "generated_from": "src/build_sites.py",
        "target_state_fips": "51",
        "grantee_site_count": len(grantees),
        "rural_clinic_count": len(rural),
        "provenance": {
            "grantee.identity": {"source_id": "hrsa_hscd_sites", "status": "real"},
            "grantee.location": {"source_id": "hrsa_hscd_sites", "status": "real"},
            "grantee.operatingHoursPerWeek": {"source_id": "hrsa_hscd_sites", "status": "real"},
            "ruralClinic.identity": {"source_id": "cms_hcris_rhc", "status": "real"},
            "ruralClinic.physicianVisits": {"source_id": "cms_hcris_rhc",
                                             "status": "real (partial: not every clinic has a recent settled cost report)"},
            "ruralClinic.hpsaScore": {"source_id": "hrsa_hpsa",
                                       "status": "real (partial: only unambiguous facility-name matches)"},
            "ruralClinic.location": {"source_id": "cms_hcris_rhc",
                                      "status": "real; precision varies -- see each record's geoSource"},
            "countyBurden": {"source_id": "cdc_places", "status": "real"},
        },
        "sites": sites,
    }


def _clean(d: dict) -> dict:
    return {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in d.items()}


def main() -> int:
    refresh = "--refresh" in sys.argv
    result = build(refresh=refresh)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(f"\nWrote {OUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  {result['grantee_site_count']} grantee sites, {result['rural_clinic_count']} rural clinics")
    return 0


if __name__ == "__main__":
    sys.exit(main())
