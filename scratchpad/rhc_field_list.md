# Rural Health Clinic dataset — field list

`dashboard/data/clinic_sites.json`, `kind: "rural_clinic"` records. 40 Virginia clinics total. Built by `src/ingestion/rural_health_clinics.py`.

## Identity & location

| Field | Type | Source | Coverage | Sample values |
|---|---|---|---|---|
| `id` | string | derived (CMS CCN) | 40/40 | `"ccn-498950"`, `"ccn-493843"` |
| `name` | string | CMS HCRIS (`RHC17_PRVDR_ID_INFO`) | 40/40 | `"TWIN COUNTY URGENT CARE"`, `"BLUEFIELD INTERNAL MEDICINE"` |
| `address` | string | CMS HCRIS | 40/40 | `"961 EAST STUART DRIVE"`, `"2111 COLLEGE AVENUE"` |
| `city` | string | CMS HCRIS | 40/40 | `"GALAX"`, `"CHILHOWIE"`, `"LEXINGTON"` |
| `county_fips` | string (5-digit FIPS) | derived — HPSA county, HCRIS county field, or geocoder, in that priority order | 40/40 | `"51640"`, `"51173"`, `"51185"` |
| `countyNameRaw` | string | CMS HCRIS (as filed — not always populated for independent cities) | 30/40 | `"CARROLL"`, `"SMYTH"`, `"TAZEWELL"` |
| `lat` / `lon` | float | see `geoSource` | 40/40 | `36.67995, -80.89597` |
| `geoSource` | enum | derived | 40/40 | `"geocoded"` (29), `"zip_centroid"` (7), `"hpsa"` (4) — precision flag, see below |

**`geoSource` meanings:**
- `hpsa` — exact coordinates from a matched HRSA HPSA facility record (highest precision)
- `geocoded` — Census Geocoder matched the street address (real street-level point)
- `geocoded_city_centroid` — street address didn't resolve; positioned at the city centroid instead
- `zip_centroid` — nothing resolved at all; positioned at the ZIP code's centroid (Census Gazetteer) — lowest precision, still real Census geography, just coarse

## HPSA shortage designation (facility-level, real, partial coverage)

| Field | Type | Source | Coverage | Sample values |
|---|---|---|---|---|
| `hpsaScore` | int (0–25ish, higher = more severe) | HRSA HPSA | **4/40** | `9`, `15`, `18` (median 16.5 among matched) |
| `hpsaStatus` | enum | HRSA HPSA | 4/40 | `"Designated"` (3), `"Withdrawn"` (1) |

Only matched when a clinic's name uniquely (or unambiguously, after cleanup) corresponds to one HPSA "Rural Health Clinic" designation row. Genuinely ambiguous names (several distinct real facilities sharing a name across different counties) are intentionally left `null` rather than guessed — see `_match_hpsa` in the ingestion script for exactly which cases resolve.

## CMS cost report (HCRIS Form 222-17), most recent settled report on file

| Field | Type | Source (worksheet/line/col) | Coverage | Range (min / median / max) |
|---|---|---|---|---|
| `physicianVisits` | int | Worksheet B, Line 1, Col 2 | 24/40 | 173 / 2,943 / 15,918 |
| `totalAdjustedVisits` | int | Worksheet C, Line 6, Col 1 — all provider types | **30/40** | 1,176 / 7,284 / 45,216 |
| `costPerVisit` | float ($) | Worksheet C, Line 7, Col 1 — scale-normalized | **30/40** | $65.52 / $189.75 / $320.41 |
| `totalAllowableCost` | int ($) | Worksheet C, Line 1, Col 1 | **30/40** | $230,626 / $1,237,386 / $7,592,621 |
| `costReportAsOf` | date (fiscal year end) | HCRIS | 30/40 | ranges 2018-12-31 to 2025-12-31 (not all clinics have a *recent* report) |

All four codes verified against CMS's own Provider Reimbursement Manual II Ch.46 Table 3 crosswalk, not guessed. `null` where a clinic hasn't filed a recent settled cost report.

## County-level context (real, but not facility-specific)

| Field | Type | Source | Coverage | Range (min / median / max) |
|---|---|---|---|---|
| `countyBurden.bphigh` | float (%) | CDC PLACES, clinic's county | 40/40 | 30.0 / 36.3 / 42.6 |
| `countyBurden.diabetes` | float (%) | CDC PLACES | 40/40 | 9.1 / 12.4 / 16.6 |
| `countyBurden.depression` | float (%) | CDC PLACES | 40/40 | 23.1 / 26.8 / 28.9 |
| `countyBurden.smoking` | float (%) | CDC PLACES | 40/40 | 10.3 / 18.8 / 22.2 |

**Important caveat:** these are the clinic's *county's* prevalence rates, not something measured at the clinic. RHCs have no facility-level PLACES equivalent. 21 distinct counties are represented across the 40 clinics, so several clinics in the same county will show identical `countyBurden` values.

## Sample full record

```json
{
  "id": "ccn-498914",
  "name": "BLUEFIELD INTERNAL MEDICINE",
  "address": "2111 COLLEGE AVENUE",
  "city": "BLUEFIELD",
  "county_fips": "51185",
  "countyNameRaw": "TAZEWELL",
  "lat": 37.24619, "lon": -81.24233,
  "geoSource": "hpsa",
  "hpsaScore": 15.0, "hpsaStatus": "Withdrawn",
  "physicianVisits": 6044.0,
  "totalAdjustedVisits": 10685.0,
  "costPerVisit": 204.75,
  "totalAllowableCost": 2243560.0,
  "costReportAsOf": "2022-12-31",
  "countyBurden": { "bphigh": 36.3, "diabetes": 12.4, "depression": 28.6, "smoking": 18.8 }
}
```

## What this means for a glyph design

- **Universal fields (40/40):** identity, location, county burden context — safe for every glyph.
- **Strong partial coverage (30/40, ~75%):** the three Worksheet-C cost report fields — good candidates for a primary encoded axis, with an honest "no data on file" treatment for the other 25%.
- **Weak coverage (4/40, 10%):** HPSA score — better as a badge/highlight than a primary axis, given how few clinics have it.
- **`costPerVisit`** is the most naturally "glyph-sizeable" financial field since it's already normalized per visit rather than raw scale (unlike `totalAllowableCost` or `totalAdjustedVisits`, which mostly just track clinic size).
