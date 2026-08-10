# County health indicators: beyond Pillar 4 (Advanced Analytics & County Intelligence epic)

**Code** `src/build_dataset.py` (aggregation), `src/ingestion/hrsa_hpsa_mental_health.py`,
`src/ingestion/hrsa_hpsa_dental_health.py` · **Catalog**
`data_source_catalog/config/data_sources.yml` · **Dashboard**
`dashboard/app/views/county.js`'s `ExpandedProfile` panel.

County profiles previously surfaced only CDC PLACES chronic-disease prevalence
(diabetes, obesity, mental distress, high blood pressure) plus the five SDoH
domain scores. This expands the profile with five additional real,
county-level indicators spanning Healthcare Access and Population Health, and
scaffolds two more (Social Vulnerability Index, Area Deprivation Index) for
future integration. All five new indicators reuse data already reachable by
this pipeline -- no new data-sharing agreement or paid license was needed.

## The five new indicators

### Mental-health HPSA score (`hpsaScoreMentalHealth`)
- **Source:** HRSA Health Professional Shortage Area designations, filtered to
  the Mental Health discipline (`hrsa_hpsa_mental_health` in the catalog).
  Sibling of the existing Primary Care HPSA feed
  (`BCD_HPSA_FCT_DET_MH.csv` vs. `..._PC.csv`).
- **Update frequency:** HRSA updates designations on an ongoing basis; no
  fixed publication calendar (documented as such in the catalog entry).
- **Limitations:** Mental-health shortage designations are sparser than
  primary care. Of 133 counties, 133 resolved to a real value in this run
  (checked at build time) -- but that will vary release to release, and a
  `null` here means "no designated shortage area," not "no shortage."
- **Quality/completeness:** Real data, same ingestion shape as the
  already-trusted primary-care HPSA score, same limitations (HPSA boundaries
  don't always align to county lines; a county-level average can mask
  sub-county variation).

### Dental HPSA score (`hpsaScoreDental`)
- **Source:** `BCD_HPSA_FCT_DET_DH.csv`, filtered to Dental Health
  (`hrsa_hpsa_dental_health`).
- **Update frequency / limitations:** Same as mental-health HPSA above.
- **Quality/completeness:** 112 of 133 counties resolved to a real value at
  last build (checked directly against the live HRSA file); the remaining 21
  have no designated dental shortage area.

### Leading chronic-disease hospitalization risk (`chronicDiseaseRisk`)
- **Source:** Virginia Dept. of Health chronic-disease hospitalization by
  geography (`virginia_chronic_disease_hospitalization`, already in the
  catalog and already fetched by this pipeline -- this story only adds the
  per-county aggregation, no new fetch). Twelve tracked conditions
  (Alzheimer's, Arthritis, Asthma, Cardiovascular Disease, CKD, COPD,
  Dementia, Diabetes, High Cholesterol, Hypertension, Ischemic Heart Disease,
  Stroke).
- **Transformation:** per county, the condition with the highest age-adjusted
  rate per 100,000 in that county's most recently reported year --
  `{leadingCondition, rate, asOfYear}`.
- **Update frequency:** annual VDH release.
- **Limitations:** This is **hospitalization** risk, not prevalence -- it
  measures who ended up admitted, not who has the condition, so it's a
  different (and complementary) signal from the CDC PLACES prevalence already
  shown in "Chronic outcomes." Picking a single "leading" condition discards
  the other eleven; a county with a close second place doesn't show it.
- **Quality/completeness:** 127 of 133 counties resolved to a real value.
  **This uncovered and fixed a pre-existing bug**: the ingestion module's
  county-name matching (`_normalize_county_name` in
  `src/ingestion/virginia_chronic_disease_hospitalization.py`) used a
  case-sensitive, unanchored regex that never actually matched "County"/"City"
  suffixes against the reference geojson, so this frame silently returned zero
  rows every build (masked because the frame was excluded from the county
  merge and nothing downstream ever inspected it). Fixed to an anchored,
  case-insensitive match. Fixing it also surfaced a second, unrelated defect:
  `dashboard/data/va-counties.geojson` carries a stale duplicate feature for
  FIPS `51515` (Bedford, an independent city retired into Bedford County
  `51019` in 2013) under the same name as the real county -- left as-is in the
  shared geojson (out of scope here; it feeds every map in the app), but
  explicitly excluded inside this one ingestion module so hospitalization data
  can never be mis-attributed to the retired code.

### FQHC site count (`fqhcSiteCount`)
- **Source:** HRSA Health Center Service Delivery and Look-Alike Sites
  (`hrsa_hscd_sites`), already ingested by `src/ingestion/hscd_sites.py` for
  the separate site-map view. This story adds the catalog registration (it
  had none before) and a per-county count.
- **Transformation:** counts active sites per `county_fips` from the
  pre-built `dashboard/data/clinic_sites.json` (produced by
  `src/build_sites.py`, run separately from the county-atlas build).
- **Update frequency:** as fresh as the last `python src/build_sites.py` run;
  not regenerated automatically by `src/build_dataset.py`.
- **Limitations:** Look-Alikes (FQHC-equivalent but not federally funded) are
  counted alongside true FQHCs; the underlying site record doesn't currently
  distinguish them. `0` is a real, meaningful count once the artifact loads
  successfully -- only a missing `clinic_sites.json` file produces `null`.
- **Quality/completeness:** Real data, 238 site rows across Virginia at last
  build.

### Rural Health Clinic count (`ruralClinicCount`)
- **Source:** CMS HCRIS Rural Health Clinic cost reports matched to HRSA HPSA
  facility points (`cms_hcris_rhc`, `src/ingestion/rural_health_clinics.py`),
  same `clinic_sites.json` artifact as above.
- **Limitations:** This ingestion module is expensive (bulk CMS ZIP downloads
  plus rate-limited Census geocoding for unmatched addresses) and is
  deliberately **not** re-run as part of every `build_dataset.py` build --
  county counts are only as fresh as the last deliberate
  `python src/build_sites.py`. Not every clinic has a recent settled cost
  report (documented as a partial-coverage limitation in the source module
  itself).
- **Quality/completeness:** Real data, 40 site rows across Virginia at last
  build.

## Missing-vs-zero, FIPS, and provenance conventions (unchanged, extended)

- FIPS codes: every new field keys off the same standardized 5-digit
  `county_fips` the rest of the pipeline already enforces
  (`.str.zfill(5)`, filtered to Virginia's `51` prefix). No new geography
  representation was introduced.
- Missing vs. zero: `hpsaScoreMentalHealth`, `hpsaScoreDental`, and
  `chronicDiseaseRisk` follow the existing `_num()` convention (`None` for
  "we have no data," never a fabricated `0`/`50`). `fqhcSiteCount` and
  `ruralClinicCount` are the one deliberate exception, matching the
  pre-existing `hpsaScore`/`patients` pattern: `0` is a legitimate, real count
  once the source artifact loaded, and `None` is reserved for "the whole
  artifact was unavailable."
- Provenance: all five fields are registered in `FIELD_SOURCE`
  (`src/build_dataset.py`) and checked by `_assert_traceable()`, so the
  Methods page's provenance table picks them up automatically, the same way
  every existing field does.

## Data source analysis: candidates evaluated, not yet integrated

Evaluated against the story's full candidate list. Sources actually
implemented above are omitted from this table.

| Source | Geographic coverage | Availability | Refresh cadence | Licensing | Integration complexity | Expected value |
|---|---|---|---|---|---|---|
| CDC/ATSDR Social Vulnerability Index | Tract → county (US) | Free, keyless bulk CSV | Every 2 years | Public domain | Medium -- tract-to-county population weighting, same pattern as `usda_food_access.py` | High -- single composite SDoH score, widely used, directly comparable to other counties nationally |
| Area Deprivation Index (ADI) | Block group → county (US) | Free for non-commercial/academic use, requires registered download | Irregular, tied to ACS vintage | **Non-commercial/academic only** -- verify before any production use | Medium-high -- registration flow, block-group aggregation | High -- the most widely cited deprivation index in rural-health literature |
| County Health Rankings & Roadmaps | County (US) | Free, annual CSV | Annual | Public domain (Robert Wood Johnson Foundation) | Low -- pre-aggregated at county level already | High -- broad, well-validated, would let this project benchmark against a national ranking directly |
| SAMHSA (substance use / behavioral health) | County or larger, varies by dataset | Mixed; some public-use files, some restricted | Varies | Mixed; check per dataset | Medium-high -- SAMHSA's county-level behavioral-health data is thinner than PLACES; may require state-level VDH substitution | High -- directly requested (opioid overdose, substance use disorder rates) and the project has no behavioral-health-specific source today beyond CDC PLACES' single "mental distress" measure |
| EPA (drinking water quality, environmental hazard) | Varies (facility, watershed, county) | Free, public APIs (ECHO, SDWIS) | Varies | Public domain | Medium -- facility-level data needs a spatial join to county, similar to the existing `cdc_eji.py` pattern | Medium -- environmental burden is already partially covered by CDC EJI; water quality specifically is a genuine gap |
| FEMA National Risk Index | Tract/county (US) | Free, public CSV | Periodic | Public domain | Low -- already published at county level | Medium -- "natural disaster risk" is on the candidate list but is a lower-priority fit for a chronic-care/primary-care planning tool |
| USDA Rural Atlas | County (US) | Free, public CSV | Periodic | Public domain | Low | Medium -- overlaps with the existing USDA food-access and RUCC rurality sources already in the pipeline |
| VDH / Virginia Health Information | Varies | Mixed; some public dashboards, some requiring a data-use agreement | Varies | Mixed | Medium -- Virginia-specific, no standard national schema to reuse | High -- most directly relevant to this project's Virginia-only scope, but requires per-dataset evaluation |
| CMS Quality/MIPS/QPP (already stubbed) | Provider/facility | Free, public CSV | Annual | Public domain | Medium -- provider-to-county attribution needed | Medium -- clinical quality signal, but redundant with HRSA UDS once that's wired |

## Recommendations: what to integrate next

1. **County Health Rankings & Roadmaps** -- lowest integration cost (already
   county-level, no aggregation needed) for the highest breadth of new signal
   (adds mortality, health-behavior, and clinical-care sub-rankings this
   project doesn't have at all today). Best next pick.
2. **CDC/ATSDR SVI** (already scaffolded as a `StubSource`, `cdc_atsdr_svi`) --
   reuses the exact tract-to-county weighting pattern already proven in
   `usda_food_access.py`; the risk to manage is avoiding double-counting
   against the existing economic/food/access domain composites.
3. **SAMHSA / VDH behavioral health** -- highest requested value (opioid,
   substance use, suicide rates are explicitly called out and currently
   uncovered), but needs a source-by-source evaluation since SAMHSA's public
   county-level cuts are inconsistent; a Virginia-specific VDH substance-use
   dataset may be the more tractable path.
4. **ADI** -- high value but gate on confirming the non-commercial license is
   compatible with how this project is deployed before spending integration
   effort (already flagged in its catalog entry).

## Not implemented this pass

Risk-tier distribution and historical patient volume were both candidate
inputs elsewhere in this project's roadmap; neither is a *county health
burden* indicator in the sense this story asks for (one is a synthetic
per-patient model output, the other has no data source at all yet), so
neither is addressed here.
