# Data Dictionary

Every field in the dashboard dataset (`dashboard/data/clinic_atlas.json`), its
source, transformation, units, and provenance. The machine-readable lineage is
`data_source_catalog/config/field_lineage.json`; this is the human companion.
Provenance values: **real** (live source), **synthetic** (generated non-PHI),
**stub** (neutral 50 placeholder until the source is wired).

## Record identity & geography
| Field | Source | Transform | Units / range | Provenance |
|---|---|---|---|---|
| `id` | reference / Census | county FIPS | 5-digit string (e.g. `51760`) | real |
| `name` | `data/reference/va_county_region.csv` (Census names) | lookup | string | real |
| `region` | reference (centroid heuristic + curated) | lookup | one of Northern/Central/Valley/Southwest/Tidewater | approximate |
| `district` | reference (curated subset) | lookup | string or empty | partial |
| `rural` | `data/reference/va_county_rucc.csv` (USDA ERS RUCC 2023, locked) | `(rucc - 1) / 8`, so RUCC 1 (metro) = 0.0 and RUCC 9 (most rural) = 1.0; population-percentile proxy when a county is missing from the lookup | 0-1 | real (lookup) |
| `ruralityMethod` | build | records which rurality path produced `rural` (`usda_ers_rucc_2023_normalized` or the population proxy) | string | metadata |

## SDoH domains (`dom.*`, 0-100 burden; higher = more need)
| Field | Source | Transform | Provenance |
|---|---|---|---|
| `dom.economic` | `census_acs_sdoh` (poverty, uninsured, unemployment, median income) | `normalize_burden` per indicator, then mean | real w/ key, else stub |
| `dom.education` | `census_acs_sdoh` (% no HS diploma) | `normalize_burden` | real w/ key, else stub |
| `dom.food` | `usda_food_access` (LI/LA tract share) | tract to county share, then `normalize_burden` | real |
| `dom.environment` | `cdc_eji` | EJI RPL_EBM, population-weighted tract to county | real |
| `dom.access` | `hrsa_hpsa` (primary-care HPSA score) | `normalize_burden` | real |

## Raw SDoH indicators (`sdoh.*`, original percentage units)
Kept alongside the normalized domains for the "Commonwealth in Bloom"
cartogram, which wants the raw values.

| Field | Source | Units | Provenance |
|---|---|---|---|
| `sdoh.poverty_rate`, `sdoh.uninsured_rate`, `sdoh.age65_pct`, `sdoh.disability_pct`, `sdoh.no_vehicle_pct`, `sdoh.broadband_pct` | `census_acs_sdoh` | % (as published) | real w/ key, else stub |

## Composite & capacity
| Field | Source | Transform | Units / range | Provenance |
|---|---|---|---|---|
| `needIndex` | derived from `dom.*` | `need_index` (weighted, renormalized over available domains) | 0-100 | derived |
| `patients` | `county_population_estimates` | county total population | integer | real w/ key, else stub (0) |
| `hpsaScore` | `hrsa_hpsa` | mean designated primary-care HPSA score | 0-26 | real |

## Health outcomes (`outcomes.*`, % of adults)
All from `cdc_places`, age-adjusted county prevalence, provenance real:
`diabetes`, `obesity`, `mhlth` (frequent mental distress), `bphigh` (high blood
pressure), `depression`, `smoking`.

## Live chronic disease feed (Virginia Open Data)
Sourced from the Virginia Open Data CKAN resource for county-level chronic
disease hospitalizations and age-adjusted rates
(`src/ingestion/virginia_chronic_disease_hospitalization.py`), loaded into the
chronic history dashboard.

| Field | Source | Transform | Units / range | Provenance |
|---|---|---|---|---|
| `Year` | Virginia Open Data chronic disease resource | parsed as integer year | 2016-present | real |
| `Geography` | Virginia Open Data chronic disease resource | normalized for county/city matching and detail labels | free-text locality name (e.g. `Fairfax County`) | real |
| `Indicator` | Virginia Open Data chronic disease resource | preserved as dashboard condition value | free-text disease / condition name | real |
| `Hospitalization Count` | Virginia Open Data chronic disease resource | read as integer count | non-negative integer | real |
| `Age-Adjusted Rate per 100,000` | Virginia Open Data chronic disease resource | converted to numeric rate | per 100,000 | real |
| `county_fips` | derived from GeoJSON county lookup | mapped using locality name + FIPS resolution | 5-digit FIPS string | derived real |
| `county` | derived from live record + county lookup | normalized display name preserving county/city distinction | string | derived real |
| `countyFips` | derived from live feed / county lookup | used to align with the map geometry and county selection | 5-digit FIPS string | derived real |
| `condition` | derived from `Indicator` | normalized for filter and grouping logic | string | derived real |
| `rate` | derived from `Age-Adjusted Rate per 100,000` | numeric value for choropleth and detail cards | rate per 100,000 | derived real |
| `cases` | derived from `Hospitalization Count` | numeric value for cards and summaries | non-negative integer | derived real |
| `year` | derived from `Year` | normalized integer used in date filters | integer year | derived real |

### Source and vintage metadata
The chronic map and county detail panel are labeled with:
- Source: Virginia Open Data
- Vintage: the selected year range from the dashboard (for example, 2016-2024)

## Clinical quality measures (`measures.*`, % of eligible)
| Field | Source | Provenance |
|---|---|---|
| `measures.htn_control`, `dm_poor`, `depr_screen`, `cervical_screen`, `child_immun` | `hrsa_uds` | stub (not wired; the pipeline emits neutral 50s badged pending) |

Note: the copy of `clinic_atlas.json` currently committed carries non-50 values
here with a `real` badge. That artifact predates the current stub code and gets
overwritten on the next build.

## Synthetic clinical
| Field | Source | Note |
|---|---|---|
| `patientsList` | `synthetic_clinical_dataset` | Synthetic, non-PHI roster shown in the Worklist and County views. Each patient carries the county's SDoH join context (`sdohJoinKey`, `sdohGeoKey`, `sdohJoinStatus`, `nb.*`), a `preventable_hospitalization_flag` label, and a `surveyFeatures` block that stays `pending_survey_results` until the needs-assessment survey lands. Scored copies get `risk` / `riskTier` / drivers from `src/model/score.py`. |

## Build metadata
| Field | Meaning |
|---|---|
| `provenance` | map of field-group to `{source_id, status}`; drives the dashboard badges |
| `sdoh_join_coverage` | audit block for the community-to-patient geographic join (matched/unmatched counts, join key) |
| `county_count`, `generated_from`, `target_state_fips` | build header |

## Notifiable-disease surveillance (`cdc_nndss`, US-048/049)
State-level weekly series. NNDSS has no county dimension, so nothing here is a
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
| `roll_mean_4/8`, `roll_std_4/8` | rolling stats over weeks before the target (`shift(1)` then roll) |
| `woy_sin`, `woy_cos` | week-of-year as a cycle, so week 52 neighbours week 1 |

### County allocation
| Field | Meaning |
|---|---|
| `population_share` | county population / state total |
| `allocated_value` | state value x `population_share` |
| `allocation_method` | `population_share_of_state` |
| `is_observed` | always `false`; allocated, never measured |
