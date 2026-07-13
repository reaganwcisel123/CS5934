"""Build the county-level dataset the live dashboard consumes.

Pipeline:
    catalog -> run each source (real / synthetic / stub, degrading gracefully)
            -> join on county_fips -> normalize to 0-100 domains
            -> assemble records in the dashboard's CLINICS schema
            -> stamp per-field provenance -> write dashboard/data/clinic_atlas.json

Every emitted field is checked against the catalog: its source_id must exist in
data_sources.yml (so any field traces back to a catalog entry).

Run:
    python src/build_dataset.py            # fetch real sources (needs network + CENSUS_API_KEY)
    python src/build_dataset.py --refresh  # ignore data/raw cache and re-fetch
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python src/build_dataset.py` (not just `python -m src.build_dataset`)
# by putting the repo root on the path before importing the src package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.catalog import Catalog, REPO_ROOT
from src.ingestion.base import Provenance
from src.ingestion.registry import REGISTRY
from src.transform import metrics
from src.transform import normalize as norm
from src.transform.geographic_join import (
    RURALITY_METHOD_POPULATION_PROXY,
    join_sdoh_to_patients,
    summarize_join_coverages,
)

OUT_PATH = REPO_ROOT / "dashboard" / "data" / "clinic_atlas.json"
REGION_REF = REPO_ROOT / "data" / "reference" / "va_county_region.csv"
REGIONS = ["Northern", "Central", "Valley", "Southwest", "Tidewater"]

# How each 0-100 SDoH domain is built from normalized raw indicators.
# (indicator column, direction): "up" = higher raw value is more burden.
DOMAIN_SPEC = {
    "economic": [("poverty_rate", "up"), ("uninsured_rate", "up"),
                 ("unemployment_rate", "up"), ("median_household_income", "down")],
    "education": [("pct_no_hs_diploma", "up")],
    "food": [("low_income_low_access_share", "up")],  # + hud_housing (stub)
    "access": [("primary_care_hpsa_score", "up")],
    # "environment" comes from epa_ejscreen (stub) -> filled as placeholder.
}
OUTCOME_FIELDS = ["diabetes", "obesity", "mhlth", "bphigh"]      # cdc_places (real)
MEASURE_FIELDS = ["htn_control", "dm_poor", "depr_screen",
                  "cervical_screen", "child_immun"]              # hrsa_uds (stub)
NEED_WEIGHTS = {"economic": 0.25, "education": 0.15, "food": 0.20,
                "environment": 0.15, "access": 0.25}

# Which catalog source_id backs each dashboard field group (for provenance).
FIELD_SOURCE = {
    "dom.economic": "census_acs_sdoh", "dom.education": "census_acs_sdoh",
    "dom.food": "usda_food_access", "dom.environment": "epa_ejscreen",
    "dom.access": "hrsa_hpsa", "hpsaScore": "hrsa_hpsa",
    "patients": "county_population_estimates",
    "outcomes": "cdc_places", "measures": "hrsa_uds",
    "patientsList": "synthetic_clinical_dataset",
}


def _run_source(cls, catalog, counties, refresh):
    """Run one source, returning (DataFrame|None, status). Never raises."""
    src = cls(catalog)
    try:
        if src.provenance == Provenance.STUB:
            src.stub_counties = counties
            return src.run(), Provenance.STUB
        if src.source_id == "synthetic_clinical_dataset":
            src.counties = counties
            return src.run(), Provenance.SYNTHETIC
        return src.run(use_cache=not refresh), Provenance.REAL
    except Exception as exc:  # network down, missing key, schema drift
        print(f"  [warn] {src.source_id} unavailable: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return None, "unavailable"


def _county_spine(real_frames: dict[str, pd.DataFrame], region_ref: pd.DataFrame) -> list[str]:
    """The master county list: union of counties seen in real data, else the
    curated reference set (offline fallback)."""
    seen: set[str] = set()
    for df in real_frames.values():
        if df is not None:
            seen.update(df["county_fips"].astype(str))
    if not seen:
        seen = set(region_ref["county_fips"].astype(str))
    return sorted(seen)


def _region_lookup(region_ref: pd.DataFrame, county_fips: list[str]) -> dict[str, dict]:
    """Map every county to a region/district. Curated where known; deterministic
    placeholder otherwise (flagged so the map can be completed later)."""
    known = region_ref.set_index("county_fips").to_dict("index")
    out = {}
    for fips in county_fips:
        if fips in known:
            out[fips] = {**known[fips], "region_source": "curated"}
        else:
            region = REGIONS[int(fips[-3:]) % len(REGIONS)]  # deterministic placeholder
            out[fips] = {"county_name": f"County {fips}", "region": region,
                         "district": "Unassigned", "region_source": "placeholder"}
    return out


def build(refresh: bool = False) -> dict:
    catalog = Catalog.load()
    region_ref = pd.read_csv(REGION_REF, dtype={"county_fips": str}).fillna("")

    # 1. Run real sources first to discover the county spine.
    real_ids = [sid for sid, cls in REGISTRY.items()
                if cls.provenance in (Provenance.REAL, Provenance.SYNTHETIC)
                and sid != "synthetic_clinical_dataset"]
    frames, status = {}, {}
    for sid in real_ids:
        frames[sid], status[sid] = _run_source(REGISTRY[sid], catalog, None, refresh)

    counties = _county_spine(frames, region_ref)
    regions = _region_lookup(region_ref, counties)
    print(f"Counties in build: {len(counties)}")

    # 2. Run county-dependent sources (synthetic roster + stubs).
    synth_df, status["synthetic_clinical_dataset"] = _run_source(
        REGISTRY["synthetic_clinical_dataset"], catalog, counties, refresh)
    for sid, cls in REGISTRY.items():
        if cls.provenance == Provenance.STUB and getattr(cls, "stub_columns", []):
            frames[sid], status[sid] = _run_source(cls, catalog, counties, refresh)

    # 3. Merge all indicator frames on county_fips.
    merged = pd.DataFrame({"county_fips": counties})
    for df in frames.values():
        if df is not None and set(df.columns) != {"county_fips"}:
            merged = merged.merge(df, on="county_fips", how="left")
    merged = merged.set_index("county_fips")

    # 4. Normalize indicators -> 0-100 domains.
    dom_frames: dict[str, pd.Series] = {}
    available_domains: set[str] = set()
    for domain, spec in DOMAIN_SPEC.items():
        parts = []
        for col, direction in spec:
            if col in merged.columns and merged[col].notna().any():
                parts.append(norm.normalize_burden(merged[col], direction))
        if parts:
            dom_frames[domain] = pd.concat(parts, axis=1).mean(axis=1)
            available_domains.add(domain)
        else:
            dom_frames[domain] = pd.Series(50.0, index=merged.index)  # placeholder
    # environment domain from epa_ejscreen (stub) -> placeholder 50.
    env = frames.get("epa_ejscreen")
    if env is not None and "environmental_burden_percentile" in env.columns:
        dom_frames["environment"] = env.set_index("county_fips")["environmental_burden_percentile"]
        if status.get("epa_ejscreen") == Provenance.REAL:
            available_domains.add("environment")
    else:
        dom_frames["environment"] = pd.Series(50.0, index=merged.index)

    dom_df = pd.DataFrame(dom_frames).round(1)

    # 5. Assemble records in the dashboard's CLINICS schema.
    synth_by_county = (synth_df.set_index("county_fips").to_dict("index")
                       if synth_df is not None else {})
    uds = frames.get("hrsa_uds")
    uds_by_county = uds.set_index("county_fips").to_dict("index") if uds is not None else {}
    pop_max = merged.get("county_population_total", pd.Series(dtype=float)).max() or 1

    records = []
    join_coverages = []
    for fips in counties:
        # Unknown domain -> neutral 50 (never None, so the need-index math is safe).
        dom = {k: (_num(dom_df.at[fips, k]) if fips in dom_df.index else None) or 50.0
               for k in NEED_WEIGHTS}
        need = metrics.need_index(dom, NEED_WEIGHTS, available_domains or set(NEED_WEIGHTS))
        pop = _num(merged.at[fips, "county_population_total"]) if "county_population_total" in merged.columns else None
        rurality = round(1 - (pop / pop_max), 2) if pop else 0.0  # population-based proxy
        roster = synth_by_county.get(fips, {}).get("patientsList", [])
        sdoh_context = {
            fips: {
                "dom": dom,
                "rural": rurality,
                "ruralityMethod": RURALITY_METHOD_POPULATION_PROXY,
                "needIndex": need,
            }
        }
        roster, coverage = join_sdoh_to_patients(roster, sdoh_context)
        join_coverages.append(coverage)
        records.append({
            "id": fips,
            "name": regions[fips]["county_name"],
            "district": regions[fips]["district"],
            "region": regions[fips]["region"],
            "rural": rurality,
            "dom": dom,
            "needIndex": need,
            "patients": int(pop) if pop else 0,
            "hpsaScore": _int(merged.at[fips, "primary_care_hpsa_score"]) if "primary_care_hpsa_score" in merged.columns else 0,
            "outcomes": {o: _num(merged.at[fips, o]) if o in merged.columns else None for o in OUTCOME_FIELDS},
            "measures": {m: _num(uds_by_county.get(fips, {}).get(m)) for m in MEASURE_FIELDS},
            "patientsList": roster,
        })

    # 6. Provenance + catalog traceability check.
    provenance = _provenance(status)
    _assert_traceable(provenance, catalog)

    return {
        "generated_from": "src/build_dataset.py",
        "target_state_fips": "51",
        "county_count": len(records),
        "sdoh_join_coverage": summarize_join_coverages(join_coverages).to_dict(),
        "provenance": provenance,
        "records": records,
    }


def _provenance(status: dict[str, str]) -> dict[str, dict]:
    out = {}
    for field, sid in FIELD_SOURCE.items():
        st = status.get(sid, "stub")
        st = "stub" if st == "unavailable" else st
        out[field] = {"source_id": sid, "status": st}
    return out


def _assert_traceable(provenance: dict[str, dict], catalog: Catalog) -> None:
    """Every emitted field's source_id must exist in the catalog."""
    unknown = [p["source_id"] for p in provenance.values()
               if p["source_id"] not in {s["source_id"] for s in catalog.sources}]
    if unknown:
        raise SystemExit(f"Traceability FAILED: source_id(s) not in catalog: {unknown}")
    print(f"Traceability OK: all {len(provenance)} field groups map to catalog sources.")


def _num(v):
    return None if v is None or pd.isna(v) else round(float(v), 1)


def _int(v):
    return 0 if v is None or pd.isna(v) else int(round(float(v)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="ignore data/raw cache, re-fetch")
    ap.add_argument("--seed", action="store_true", help="seed the catalog into the DB (needs DATABASE_URL)")
    ap.add_argument("--to-db", action="store_true", help="upsert the built dataset into the DB")
    ap.add_argument("--score", action="store_true", help="attach model risk tiers to patients (needs a trained model)")
    args = ap.parse_args()

    if args.seed:  # mirror the catalog into data_source + field_lineage
        from src.db import writer
        cat = Catalog.load()
        ns, nl = writer.seed_catalog(cat.sources, cat.lineage)
        print(f"Seeded catalog: {ns} sources, {nl} lineage rows")

    print("Building clinic atlas dataset from the data source catalog...")
    result = build(refresh=args.refresh)

    if args.score:  # attach per-patient risk tiers + drivers from the trained model
        from src.model import score
        model = score.load_patient_model()
        if model is None:
            print("  --score skipped: no trained model (run `python -m src.model.train`).")
        else:
            n = score.score_records(result["records"], model)
            print(f"  Scored {n} patients with risk tiers + drivers.")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # allow_nan=False: fail loudly rather than emit NaN, which is invalid JSON.
    OUT_PATH.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")

    real = [f for f, p in result["provenance"].items() if p["status"] in ("real", "synthetic")]
    stub = [f for f, p in result["provenance"].items() if p["status"] == "stub"]
    print(f"\nWrote {OUT_PATH.relative_to(REPO_ROOT)} ({result['county_count']} counties)")
    print(f"  REAL/SYNTHETIC fields: {', '.join(real)}")
    print(f"  STUB fields:           {', '.join(stub)}")

    if args.to_db:  # upsert into Postgres
        from src.db import writer
        n = writer.load_dataset(result["records"], result["provenance"])
        print(f"Loaded {n} counties into the database.")
    return 0


if __name__ == "__main__":
    sys.exit(main())