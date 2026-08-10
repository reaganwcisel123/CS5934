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

from dotenv import load_dotenv

# Repo root on sys.path so `python src/build_dataset.py` works without -m.
REPO_ROOT_PATH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT_PATH))

load_dotenv(REPO_ROOT_PATH / ".env")

import pandas as pd

from src.catalog import Catalog, REPO_ROOT
from src.ingestion.base import Provenance
from src.ingestion.registry import REGISTRY
from src.transform import metrics
from src.transform import normalize as norm
from src.transform.geographic_join import (
    RURALITY_METHOD_POPULATION_PROXY,
    RURALITY_METHOD_RUCC_2023,
    join_sdoh_to_patients,
    summarize_join_coverages,
)

OUT_PATH = REPO_ROOT / "dashboard" / "data" / "clinic_atlas.json"
REGION_REF = REPO_ROOT / "data" / "reference" / "va_county_region.csv"

# Pre-built by src/build_sites.py (point-level FQHC/RHC sites, not part of this
# module's own county merge -- see hrsa_hscd_sites / cms_hcris_rhc in the catalog).
CLINIC_SITES_PATH = REPO_ROOT / "dashboard" / "data" / "clinic_sites.json"

# Locked rurality source: USDA ERS Rural-Urban Continuum Codes 2023 (US-007).
RUCC_REF = REPO_ROOT / "data" / "reference" / "va_county_rucc.csv"

REGIONS = ["Northern", "Central", "Valley", "Southwest", "Tidewater"]

# How each 0-100 SDoH domain is built from normalized raw indicators.
# (indicator column, direction): "up" = higher raw value is more burden.
DOMAIN_SPEC = {
    "economic": [
        ("poverty_rate", "up"),
        ("uninsured_rate", "up"),
        ("unemployment_rate", "up"),
        ("median_household_income", "down"),
    ],
    "education": [
        ("pct_no_hs_diploma", "up"),
    ],
    "food": [
        ("low_income_low_access_share", "up"),
    ],  # + hud_housing (stub)
    "access": [
        ("primary_care_hpsa_score", "up"),
    ],
    # "environment" comes from cdc_eji
    # (real Environmental Burden Module percentile).
}

OUTCOME_FIELDS = [
    "diabetes",
    "obesity",
    "mhlth",
    "bphigh",
    "depression",
    "smoking",
]  # cdc_places (real)

MEASURE_FIELDS = [
    "htn_control",
    "dm_poor",
    "depr_screen",
    "cervical_screen",
    "child_immun",
]  # hrsa_uds (stub)

# Raw ACS SDoH indicators consumed directly by the bloom cartogram,
# kept in their original percentage units (not normalized).
SDOH_FIELDS = [
    "poverty_rate",
    "uninsured_rate",
    "age65_pct",
    "disability_pct",
    "no_vehicle_pct",
    "broadband_pct",
]

NEED_WEIGHTS = {
    "economic": 0.25,
    "education": 0.15,
    "food": 0.20,
    "environment": 0.15,
    "access": 0.25,
}

# Which catalog source_id backs each dashboard field group.
FIELD_SOURCE = {
    "dom.economic": "census_acs_sdoh",
    "dom.education": "census_acs_sdoh",
    "dom.food": "usda_food_access",
    "dom.environment": "cdc_eji",
    "dom.access": "hrsa_hpsa",
    "hpsaScore": "hrsa_hpsa",
    "patients": "county_population_estimates",
    "outcomes": "cdc_places",
    "measures": "hrsa_uds",
    "sdoh": "census_acs_sdoh",
    "patientsList": "synthetic_clinical_dataset",
    "chronicDiseaseRisk": "virginia_chronic_disease_hospitalization",
    "hpsaScoreMentalHealth": "hrsa_hpsa_mental_health",
    "hpsaScoreDental": "hrsa_hpsa_dental_health",
    "fqhcSiteCount": "hrsa_hscd_sites",
    "ruralClinicCount": "cms_hcris_rhc",
}


def _run_source(cls, catalog, counties, refresh):
    """Run one source, returning (DataFrame|None, status).

    Source errors do not terminate the entire build. Instead, the source is
    marked unavailable and the pipeline degrades gracefully.
    """
    src = cls(catalog)

    try:
        if src.provenance == Provenance.STUB:
            src.stub_counties = counties
            return src.run(), Provenance.STUB

        if src.source_id == "synthetic_clinical_dataset":
            src.counties = counties
            return src.run(), Provenance.SYNTHETIC

        return src.run(use_cache=not refresh), Provenance.REAL

    except Exception as exc:
        print(
            f"  [warn] {src.source_id} unavailable: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None, "unavailable"


def _county_spine(
    real_frames: dict[str, pd.DataFrame],
    region_ref: pd.DataFrame,
) -> list[str]:
    """Create the master county list.

    The county spine is the union of counties observed in real data. If no real
    data is available, the curated Virginia county reference is used.
    """
    seen: set[str] = set()

    for df in real_frames.values():
        if df is not None:
            seen.update(df["county_fips"].astype(str))

    if not seen:
        seen = set(region_ref["county_fips"].astype(str))

    return sorted(seen)


def _region_lookup(
    region_ref: pd.DataFrame,
    county_fips: list[str],
) -> dict[str, dict]:
    """Map every county to a region and district.

    Curated values are used where available. A deterministic placeholder is
    generated when a county does not exist in the reference file.
    """
    known = region_ref.set_index("county_fips").to_dict("index")
    out = {}

    for fips in county_fips:
        if fips in known:
            out[fips] = {
                **known[fips],
                "region_source": "curated",
            }
        else:
            region = REGIONS[int(fips[-3:]) % len(REGIONS)]
            out[fips] = {
                "county_name": f"County {fips}",
                "region": region,
                "district": "Unassigned",
                "region_source": "placeholder",
            }

    return out


def _chronic_risk_by_county(df: pd.DataFrame | None) -> dict[str, dict]:
    """Per county, the condition with the highest age-adjusted rate in that
    county's most recently reported year. A county absent from the dict has
    no chronic-disease hospitalization data at all -- the caller must not
    invent a 0.0 rate for it."""
    if df is None or df.empty:
        return {}

    out: dict[str, dict] = {}
    for fips, group in df.groupby("county_fips"):
        latest_year = group["year"].max()
        if pd.isna(latest_year):
            continue

        latest = group[group["year"] == latest_year]
        if latest.empty or latest["rate"].isna().all():
            continue

        top = latest.loc[latest["rate"].idxmax()]
        out[fips] = {
            "leadingCondition": str(top["condition"]),
            "rate": round(float(top["rate"]), 1),
            "asOfYear": int(latest_year),
        }

    return out


def _site_counts_by_county() -> dict[str, dict[str, int]] | None:
    """Per-county FQHC ("grantee") and Rural Health Clinic ("rural_clinic")
    site counts, aggregated from the pre-built dashboard/data/clinic_sites.json
    (src/build_sites.py; hrsa_hscd_sites + cms_hcris_rhc in the catalog).

    Returns None -- not an empty dict -- when the artifact itself is missing,
    so a caller can tell "we checked and this county has zero sites" apart
    from "we don't know how many sites this county has."
    """
    if not CLINIC_SITES_PATH.exists():
        return None

    try:
        data = json.loads(CLINIC_SITES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    counts: dict[str, dict[str, int]] = {}
    for site in data.get("sites", []):
        fips, kind = site.get("county_fips"), site.get("kind")
        if not fips or not kind:
            continue
        counts.setdefault(fips, {})
        counts[fips][kind] = counts[fips].get(kind, 0) + 1

    return counts


def build(refresh: bool = False) -> dict:
    """Build and return the complete Clinic Needs Atlas dataset."""
    catalog = Catalog.load()

    region_ref = pd.read_csv(
        REGION_REF,
        dtype={"county_fips": str},
    ).fillna("")

    # Locked rurality lookup:
    # county_fips -> USDA RUCC 2023 code (1 through 9).
    rucc_ref = pd.read_csv(
        RUCC_REF,
        dtype={"county_fips": str},
    )

    rucc_by_fips = dict(
        zip(
            rucc_ref["county_fips"].str.zfill(5),
            rucc_ref["rucc_2023"].astype(int),
        )
    )

    # -------------------------------------------------------------------------
    # 1. Run real sources first to discover the county spine.
    # -------------------------------------------------------------------------
    real_ids = [
        sid
        for sid, cls in REGISTRY.items()
        if cls.provenance in (Provenance.REAL, Provenance.SYNTHETIC)
        and sid != "synthetic_clinical_dataset"
    ]

    frames: dict[str, pd.DataFrame | None] = {}
    status: dict[str, str] = {}

    for sid in real_ids:
        frames[sid], status[sid] = _run_source(
            REGISTRY[sid],
            catalog,
            None,
            refresh,
        )

    counties = _county_spine(frames, region_ref)
    regions = _region_lookup(region_ref, counties)

    print(f"Counties in build: {len(counties)}")

    # -------------------------------------------------------------------------
    # 2. Run county-dependent sources.
    # -------------------------------------------------------------------------
    synth_df, status["synthetic_clinical_dataset"] = _run_source(
        REGISTRY["synthetic_clinical_dataset"],
        catalog,
        counties,
        refresh,
    )

    for sid, cls in REGISTRY.items():
        if (
            cls.provenance == Provenance.STUB
            and getattr(cls, "stub_columns", [])
        ):
            frames[sid], status[sid] = _run_source(
                cls,
                catalog,
                counties,
                refresh,
            )

    # -------------------------------------------------------------------------
    # 3. Merge all indicator frames on county_fips.
    # -------------------------------------------------------------------------
    merged = pd.DataFrame({"county_fips": counties})

    for sid, df in frames.items():
        # Skip frames keyed on more than county_fips (one county -> many rows);
        # merging them would multiply the spine. They feed provenance only.
        if sid == "virginia_chronic_disease_hospitalization":
            continue

        if df is not None and set(df.columns) != {"county_fips"}:
            merged = merged.merge(
                df,
                on="county_fips",
                how="left",
            )

    merged = merged.set_index("county_fips")

    # -------------------------------------------------------------------------
    # 4. Normalize indicators into 0-100 domain scores.
    # -------------------------------------------------------------------------
    dom_frames: dict[str, pd.Series] = {}
    available_domains: set[str] = set()

    for domain, spec in DOMAIN_SPEC.items():
        parts = []

        for col, direction in spec:
            if col in merged.columns and merged[col].notna().any():
                parts.append(
                    norm.normalize_burden(
                        merged[col],
                        direction,
                    )
                )

        if parts:
            dom_frames[domain] = pd.concat(
                parts,
                axis=1,
            ).mean(axis=1)

            available_domains.add(domain)
        else:
            # Unknown domain uses a neutral placeholder.
            dom_frames[domain] = pd.Series(
                50.0,
                index=merged.index,
            )

    # Environment domain from CDC EJI:
    # real Environmental Burden Module percentile.
    env = frames.get("cdc_eji")

    if (
        env is not None
        and "environmental_burden_percentile" in env.columns
    ):
        dom_frames["environment"] = env.set_index("county_fips")[
            "environmental_burden_percentile"
        ]

        if status.get("cdc_eji") == Provenance.REAL:
            available_domains.add("environment")
    else:
        dom_frames["environment"] = pd.Series(
            50.0,
            index=merged.index,
        )

    dom_df = pd.DataFrame(dom_frames).round(1)

    # -------------------------------------------------------------------------
    # 5. Assemble records in the dashboard's CLINICS schema.
    # -------------------------------------------------------------------------
    synth_by_county = (
        synth_df.set_index("county_fips").to_dict("index")
        if synth_df is not None
        else {}
    )

    uds = frames.get("hrsa_uds")

    uds_by_county = (
        uds.set_index("county_fips").to_dict("index")
        if uds is not None
        else {}
    )

    chronic_by_county = _chronic_risk_by_county(
        frames.get("virginia_chronic_disease_hospitalization")
    )

    # hrsa_hscd_sites / cms_hcris_rhc never run through the REGISTRY loop above
    # (they're point-level artifacts consumed via src/build_sites.py, not this
    # module's county merge -- see the catalog entries), so their provenance
    # has to be set explicitly rather than falling out of _run_source().
    site_counts_by_county = _site_counts_by_county()
    site_status = Provenance.REAL if site_counts_by_county is not None else "unavailable"
    status["hrsa_hscd_sites"] = site_status
    status["cms_hcris_rhc"] = site_status

    pop_max = merged.get(
        "county_population_total",
        pd.Series(dtype=float),
    ).max()

    # max() of an empty/all-NaN column is NaN (which is truthy) -> guard explicitly.
    if pd.isna(pop_max) or pop_max <= 0:
        pop_max = 1

    records = []
    join_coverages = []

    for fips in counties:
        # Unknown domain -> neutral 50; a legitimate 0.0 score must survive.
        dom = {}

        for key in NEED_WEIGHTS:
            val = (
                _num(dom_df.at[fips, key])
                if fips in dom_df.index
                else None
            )

            dom[key] = 50.0 if val is None else val

        need = metrics.need_index(
            dom,
            NEED_WEIGHTS,
            available_domains or set(NEED_WEIGHTS),
        )

        pop = (
            _num(merged.at[fips, "county_population_total"])
            if "county_population_total" in merged.columns
            else None
        )

        # Locked rurality from USDA RUCC 2023.
        #
        # RUCC 1 (metro) -> 0.0
        # RUCC 9 (most rural) -> 1.0
        rucc = rucc_by_fips.get(fips)

        if rucc is not None:
            rurality = round((rucc - 1) / 8, 2)
            rurality_method = RURALITY_METHOD_RUCC_2023
        else:
            # Fall back to the population proxy only when RUCC is unavailable.
            rurality = (
                round(1 - (pop / pop_max), 2)
                if pop
                else 0.0
            )
            rurality_method = RURALITY_METHOD_POPULATION_PROXY

        roster = synth_by_county.get(
            fips,
            {},
        ).get(
            "patientsList",
            [],
        )

        sdoh_context = {
            fips: {
                "dom": dom,
                "rural": rurality,
                "ruralityMethod": rurality_method,
                "needIndex": need,
            }
        }

        roster, coverage = join_sdoh_to_patients(
            roster,
            sdoh_context,
        )

        join_coverages.append(coverage)

        records.append(
            {
                "id": fips,
                "name": regions[fips]["county_name"],
                "district": regions[fips]["district"],
                "region": regions[fips]["region"],
                "rural": rurality,

                # Record the locked rurality method for auditability.
                "ruralityMethod": rurality_method,

                "dom": dom,
                "needIndex": need,

                "patients": int(pop) if pop else 0,

                "hpsaScore": (
                    _int(
                        merged.at[
                            fips,
                            "primary_care_hpsa_score",
                        ]
                    )
                    if "primary_care_hpsa_score" in merged.columns
                    else 0
                ),

                "outcomes": {
                    outcome: (
                        _num(merged.at[fips, outcome])
                        if outcome in merged.columns
                        else None
                    )
                    for outcome in OUTCOME_FIELDS
                },

                "measures": {
                    measure: _num(
                        uds_by_county.get(
                            fips,
                            {},
                        ).get(measure)
                    )
                    for measure in MEASURE_FIELDS
                },

                # Raw Census ACS values used by bloom.js.
                "sdoh": {
                    field: (
                        _num(merged.at[fips, field])
                        if field in merged.columns
                        else None
                    )
                    for field in SDOH_FIELDS
                },

                # Discipline-specific HPSA shortage scores, siblings of hpsaScore
                # (Primary Care). None (not 0) when this county has no
                # designated shortage area for that discipline -- absence of a
                # designation is not the same as a measured score of zero.
                "hpsaScoreMentalHealth": (
                    _num(merged.at[fips, "mental_health_hpsa_score"])
                    if "mental_health_hpsa_score" in merged.columns
                    else None
                ),
                "hpsaScoreDental": (
                    _num(merged.at[fips, "dental_health_hpsa_score"])
                    if "dental_health_hpsa_score" in merged.columns
                    else None
                ),

                # Leading preventable-hospitalization condition (VDH, real,
                # separate from CDC PLACES prevalence above). None when this
                # county has no hospitalization rows at all.
                "chronicDiseaseRisk": chronic_by_county.get(fips),

                # FQHC / Rural Health Clinic counts from the pre-built
                # clinic_sites.json. 0 is a real count once the artifact
                # loaded; None only when the whole artifact is unavailable.
                "fqhcSiteCount": (
                    site_counts_by_county.get(fips, {}).get("grantee", 0)
                    if site_counts_by_county is not None
                    else None
                ),
                "ruralClinicCount": (
                    site_counts_by_county.get(fips, {}).get("rural_clinic", 0)
                    if site_counts_by_county is not None
                    else None
                ),

                "patientsList": roster,
            }
        )

    # -------------------------------------------------------------------------
    # 6. Provenance and catalog traceability.
    # -------------------------------------------------------------------------
    provenance = _provenance(status)
    _assert_traceable(provenance, catalog)

    return {
        "generated_from": "src/build_dataset.py",
        "target_state_fips": "51",
        "county_count": len(records),
        "sdoh_join_coverage": summarize_join_coverages(
            join_coverages
        ).to_dict(),
        "provenance": provenance,
        "records": records,
    }


def _provenance(status: dict[str, str]) -> dict[str, dict]:
    """Generate field-level provenance from source execution status."""
    out = {}

    for field, sid in FIELD_SOURCE.items():
        source_status = status.get(sid, "stub")

        # Sources that failed during execution are surfaced to the dashboard
        # as stub/pending fields.
        if source_status == "unavailable":
            source_status = "stub"

        out[field] = {
            "source_id": sid,
            "status": source_status,
        }

    return out


def _assert_traceable(
    provenance: dict[str, dict],
    catalog: Catalog,
) -> None:
    """Confirm every emitted field maps to a catalog source."""
    catalog_source_ids = {
        source["source_id"]
        for source in catalog.sources
    }

    unknown = [
        item["source_id"]
        for item in provenance.values()
        if item["source_id"] not in catalog_source_ids
    ]

    if unknown:
        raise SystemExit(
            "Traceability FAILED: "
            f"source_id(s) not in catalog: {unknown}"
        )

    print(
        "Traceability OK: "
        f"all {len(provenance)} field groups map to catalog sources."
    )


def _num(value):
    """Convert a value to a rounded float or None."""
    if value is None or pd.isna(value):
        return None

    return round(float(value), 1)


def _int(value):
    """Convert a value to an integer or zero."""
    if value is None or pd.isna(value):
        return 0

    return int(round(float(value)))


def main() -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--refresh",
        action="store_true",
        help="ignore data/raw cache and re-fetch",
    )

    parser.add_argument(
        "--seed",
        action="store_true",
        help="seed the catalog into the DB (needs DATABASE_URL)",
    )

    parser.add_argument(
        "--to-db",
        action="store_true",
        help="upsert the built dataset into the DB",
    )

    parser.add_argument(
        "--score",
        action="store_true",
        help="attach model risk tiers to patients "
             "(needs a trained model)",
    )

    args = parser.parse_args()

    if args.seed:
        # Mirror the catalog into data_source + field_lineage.
        from src.db import writer

        catalog = Catalog.load()

        source_count, lineage_count = writer.seed_catalog(
            catalog.sources,
            catalog.lineage,
        )

        print(
            f"Seeded catalog: {source_count} sources, "
            f"{lineage_count} lineage rows"
        )

    print(
        "Building clinic atlas dataset "
        "from the data source catalog..."
    )

    result = build(refresh=args.refresh)

    if args.score:
        # Attach model risk:
        # patients -> tiers and drivers
        # counties -> model risk
        from src.model import score

        patient_model = score.load_patient_model()
        county_model = score.load_county_model()

        if patient_model is None and county_model is None:
            print(
                "  --score skipped: no trained models "
                "(run `python -m src.model.train`)."
            )

        if patient_model is not None:
            scored_patients = score.score_records(
                result["records"],
                patient_model,
            )

            print(
                f"  Scored {scored_patients} patients "
                "(tiers + drivers)."
            )

        if county_model is not None:
            scored_counties = score.score_counties(
                result["records"],
                county_model,
            )

            print(
                f"  Scored {scored_counties} counties "
                "(model risk)."
            )

    OUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # allow_nan=False:
    # fail loudly instead of emitting NaN, which is invalid JSON.
    OUT_PATH.write_text(
        json.dumps(
            result,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    real = [
        field
        for field, provenance in result["provenance"].items()
        if provenance["status"] in ("real", "synthetic")
    ]

    stub = [
        field
        for field, provenance in result["provenance"].items()
        if provenance["status"] == "stub"
    ]

    print(
        f"\nWrote {OUT_PATH.relative_to(REPO_ROOT)} "
        f"({result['county_count']} counties)"
    )

    print(
        f"  REAL/SYNTHETIC fields: {', '.join(real)}"
    )

    print(
        f"  STUB fields:           {', '.join(stub)}"
    )

    if args.to_db:
        from src.db import writer

        county_count = writer.load_dataset(
            result["records"],
            result["provenance"],
        )

        print(
            f"Loaded {county_count} counties into the database."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())