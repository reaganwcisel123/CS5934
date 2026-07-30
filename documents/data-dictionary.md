# Data Dictionary

Every field in the dashboard dataset (`dashboard/data/clinic_atlas.json`), its
source, transformation, units, and provenance. The machine-readable lineage is
`data_source_catalog/config/field_lineage.json`; this is the human companion.
Provenance: **real** (live source) · **synthetic** (generated non-PHI) · **stub**
(neutral 50 placeholder until wired).

## Record identity & geography
| Field | Source | Transform | Units / range | Provenance |
|---|---|---|---|---|
| `id` | reference / Census | county FIPS | 5-digit string (e.g. `51760`) | real |
| `name` | `data/reference/va_county_region.csv` (Census names) | lookup | string | real |
| `region` | reference (centroid heuristic + curated) | lookup | one of Northern/Central/Valley/Southwest/Tidewater | approximate |
| `district` | reference (curated subset) | lookup | string or empty | partial |
| `rural` | `county_population_estimates` | 1 − population percentile | 0–1 | derived (stub w/o key) |

## SDoH domains (`dom.*`, 0–100 burden; higher = more need)
| Field | Source | Transform | Provenance |
|---|---|---|---|
| `dom.economic` | `census_acs_sdoh` (poverty, uninsured, unemployment, median income) | `normalize_burden` per indicator → mean | real w/ key, else stub |
| `dom.education` | `census_acs_sdoh` (% no HS diploma) | `normalize_burden` | real w/ key, else stub |
| `dom.food` | `usda_food_access` (LI/LA tract share) | tract → county share → `normalize_burden` | real |
| `dom.environment` | `cdc_eji` | EJI RPL_EBM, population-weighted tract to county | real |
| `dom.access` | `hrsa_hpsa` (primary-care HPSA score) | `normalize_burden` | real |

## Composite & capacity
| Field | Source | Transform | Units / range | Provenance |
|---|---|---|---|---|
| `needIndex` | derived from `dom.*` | `need_index` (weighted, renormalized over available domains) | 0–100 | derived |
| `patients` | `county_population_estimates` | county total population | integer | real w/ key, else stub (0) |
| `hpsaScore` | `hrsa_hpsa` | mean designated primary-care HPSA score | 0–26 | real |

## Health outcomes (`outcomes.*`, % of adults)
| Field | Source | Transform | Provenance |
|---|---|---|---|
| `outcomes.diabetes` | `cdc_places` | age-adjusted county prevalence | real |
| `outcomes.obesity` | `cdc_places` | age-adjusted county prevalence | real |
| `outcomes.mhlth` (frequent mental distress) | `cdc_places` | age-adjusted county prevalence | real |
| `outcomes.bphigh` (high blood pressure) | `cdc_places` | age-adjusted county prevalence | real |

## Clinical quality measures (`measures.*`, % of eligible)
| Field | Source | Provenance |
|---|---|---|
| `measures.htn_control`, `dm_poor`, `depr_screen`, `cervical_screen`, `child_immun` | `hrsa_uds` | stub (not wired) |

## Synthetic clinical
| Field | Source | Note |
|---|---|---|
| `patientsList` | `synthetic_clinical_dataset` | Synthetic, non-PHI. Present in the dataset but **removed from the Signal dashboard for HIPAA safety.** |

## Build metadata
| Field | Meaning |
|---|---|
| `provenance` | map of field-group → `{source_id, status}`; drives the dashboard badges |
| `county_count`, `generated_from`, `target_state_fips` | build header |

## Notifiable-disease surveillance (`cdc_nndss`, US-048/049)
State-level weekly series. **NNDSS has no county dimension**, so nothing here is a
county observation.

| Field | Source | Transform | Provenance |
|---|---|---|---|
| `condition` | `cdc_nndss` | trimmed NNDSS `label`; the series key | real |
| `mmwr_year`, `mmwr_week` | `cdc_nndss` | MMWR year and week as integers | real |
| `cases` | `cdc_nndss` | current-week count (`m1`). Rows flagged `N`/`U`/`NC` become NULL, never 0 | real |

### Forecast panel (`src/model/forecast_dataset.py`)
| Field | Meaning |
|---|---|
| `week_idx` | monotonic week counter; ranks observed `(mmwr_year, mmwr_week)` pairs so lags cross 52- and 53-week years correctly |
| `lag_1…lag_8`, `lag_52` | `cases` shifted N weeks; `lag_52` is the seasonal term |
| `roll_mean_4/8`, `roll_std_4/8` | rolling stats over weeks **before** the target (`shift(1)` then roll) |
| `woy_sin`, `woy_cos` | week-of-year as a cycle, so week 52 neighbours week 1 |

### County allocation
| Field | Meaning |
|---|---|
| `population_share` | county population ÷ state total |
| `allocated_value` | state value × `population_share` |
| `allocation_method` | `population_share_of_state` |
| `is_observed` | always `false` — allocated, never measured |
