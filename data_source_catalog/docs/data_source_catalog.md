# Data Source Catalog

## Purpose

This file documents the data sources used by the rural health analytics
pipeline. The machine-readable source of truth is:

```text
data_source_catalog/config/data_sources.yml
```

with per-field provenance in `data_source_catalog/config/field_lineage.json`.
This Markdown file is the human-readable companion: what each source is, how
we expect to access it, and what to watch out for before ingestion. When the
two disagree, the YAML wins; run the validator
(`uv run python data_source_catalog/scripts/validate_data_catalog.py`) after
any edit.

## Catalog metadata fields

Every catalog entry has identifiers (`source_id`, `source_name`), context
(`provider`, `source_category`), and access information (`access_method`,
`access_url`, `documentation_url`, `auth_required`, `api_key_env_var`, which
holds an env var name and never a real key). Geography and timing are
described by `geographic_granularity`, `temporal_granularity`,
`refresh_cadence`, and `schema_version`. Integration fields (`join_keys`,
`fields_used`) explain how the source lands in the final dataset, and
`limitations` and `privacy_classification` record caveats. Implementation
state lives in `ingestion_status`, `ingestion_script`, and
`last_verified_date`.

## Source inventory

19 sources as of 2026-08-07. Statuses in parentheses come from
`ingestion_status` in the YAML.

| `source_id` | What it is | Access | Geography | Cadence | Status |
| --- | --- | --- | --- | --- | --- |
| `virginia_chronic_disease_hospitalization` | VDH chronic disease hospitalizations via Virginia Open Data | CKAN datastore API / CSV export | county | annual | `access_verified` |
| `cdc_places` | CDC PLACES: Local Data for Better Health | CDC data portal / Socrata API / CSV | county, place, tract, ZCTA | annual | `access_verified` |
| `grants_gov_opportunities` | Curated Grants.gov rural-health opportunity corpus | REST API (`search2` + `fetchOpportunity`) | opportunity, agency, eligibility | daily cache freshness | `validated` |
| `cdc_nwss` | CDC National Wastewater Surveillance System | CDC data portal / Socrata API / CSV | treatment plant, county, state | weekly, generally Friday | `access_verified` |
| `cdc_nndss` | CDC NNDSS weekly notifiable disease tables | Data.CDC.gov Socrata (`x9gk-5huc`) / CSV | national, state, territory | weekly provisional + annual finalized | `sample_pull_successful` |
| `hrsa_hpsa` | HRSA Health Professional Shortage Area designations | HRSA Data Warehouse / dashboard / GIS REST | shortage area, county, state, boundaries | publisher-specific | `access_verified` |
| `hrsa_uds` | HRSA Health Center Program Uniform Data System | UDS dashboard downloads (CSV/XLSX) | health center, state, national | annual | `access_verified` |
| `cms_medicare_puf` | CMS Medicare public use files | data.cms.gov API / CSV | provider, NPI, facility, county, state | dataset-specific, often annual or quarterly | `schema_reviewed` |
| `cms_mips_qpp` | CMS Quality Payment Program / MIPS public data | QPP downloads and public APIs | clinician, group, practice, state | annual | `not_started` |
| `cms_quality_stars` | CMS Provider Data Catalog star ratings | Provider Data Catalog API / CSV | facility (hospital, nursing home, home health), state | CMS scheduled refresh; see the Data Updates dataset | `access_verified` |
| `census_acs_sdoh` | ACS 5-year SDoH variables | Census Data API (`CENSUS_API_KEY` recommended) | state, county, tract, some block groups | annual | `access_verified` |
| `cdc_eji` | CDC/ATSDR Environmental Justice Index | national tract-level CSV, population-weighted to county | tract, county | periodic CDC/ATSDR releases | `access_verified` |
| `aspr_hospital_capacity` | HHS/ASPR hospital capacity (COVID-era feed) | HealthData.gov / Socrata API / CSV | facility, state | stopped updating 2024-05-03 | `deprecated_or_historical` |
| `usda_food_access` | USDA Food Access Research Atlas | Excel download / map services | census tract | irregular | `access_verified` |
| `hud_housing` | HUD FMR and income limits | HUD USER API (needs `HUD_API_TOKEN`) / downloads | county, metro, ZIP, state | annual for FMR/income limits; varies otherwise | `access_verified` |
| `grants_gov` | Grants.gov public opportunity search | REST API (`search2`) | opportunity, agency, assistance listing, eligibility | publisher-driven, continuous | `access_verified` |
| `state_health_department_feeds` | State health department feeds (states TBD) | state-specific API / dashboard / RSS / Socrata / ArcGIS | state, county, health district | varies by state | `not_started` |
| `county_population_estimates` | Census PEP county population estimates | keyless PEP bulk CSV download | county, state, nation | annual | `ingestion_wired` |
| `synthetic_clinical_dataset` | Project synthetic non-PHI clinical dataset | generated in-repo (`src/ingestion/synthetic_clinical.py`) | synthetic patient, clinic, county | regenerate per version | `ingestion_wired` |

Note there are two Grants.gov entries on purpose: `grants_gov` is the generic
opportunity-search source, while `grants_gov_opportunities` is the small
curated corpus behind the funding recommender (`src/grants/pipeline.py`).

## Notes for other team members

- `cdc_eji` replaced the retired EPA EJSCREEN source, whose download host was
  deprecated. The environment domain now comes from the CDC/ATSDR EJI
  Environmental Burden Module, population-weighted from census tracts to the
  county.
- `aspr_hospital_capacity` is `deprecated_or_historical` because the
  COVID-era HealthData.gov feed is frozen. Don't treat it as current
  hospital-capacity surveillance.
- `cdc_nndss` is state-keyed only. It has no county dimension, its `states`
  column changes casing partway through the dataset, and it pulls Virginia
  plus six neighbouring jurisdictions. Read the `limitations` list in the
  YAML before touching it.
- `state_health_department_feeds` stays generic until target states are
  picked. Once one is, add a child catalog entry per feed or state.
- `synthetic_clinical_dataset` must stay synthetic and non-PHI. Do not commit
  real patient data.
