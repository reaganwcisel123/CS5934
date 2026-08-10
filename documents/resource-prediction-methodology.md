# Methodology: clinic resource-demand prediction (Predictive Analytics epic)

**Code** `src/model/resource_prediction.py` · **Config** `data/reference/resource_planning_config.yml`
· **API** `src/api/resource_prediction.py` · **Dashboard** `dashboard/app/views/resource-plan.js`

## The two things to know first

**This is a rules engine, not a trained model.** There is no historical clinic
utilization time series anywhere in this project's data sources -- only a
cross-sectional county/patient snapshot. A trend model built on data that
doesn't exist would be fabricating history. Instead, every quantity is a
disclosed factor (a prevalence rate, a visit rate, a staffing ratio) multiplied
by an observed county indicator, the same approach
`src/model/supply_needs.py` already uses for notifiable-disease stocking. See
[Future enhancements](#future-enhancements) for the replacement path once real
utilization data exists.

**Every figure is sized off the county's total population, not one clinic's
roster.** `patients` in the atlas is the county's Census population estimate
(`county_population_estimates`), the same figure the NNDSS county forecast
already allocates against and the same population basis HRSA uses to compute
a HPSA shortage score. A prediction answers "how much primary-care capacity
does this county need in total," not "how many physicians does my specific
clinic need." Every API response and dashboard panel carries this as
`scope_note`; a clinic sizing its own order should scale every quantity by its
estimated share of the county's patient panel.

## Intended use

30/60/90-day planning for a small rural clinic: roughly how many patients to
expect, which chronic conditions will drive that volume, and what medications,
supplies, equipment, and staffing that implies. It exists to inform a stocking
and staffing conversation before a shortage happens.

**Not intended for:** individual patient care, clinical protocol, a
procurement order, or a staffing mandate. This is a capstone prototype for
academic evaluation, not a production clinical or operational planning tool.

## Inputs

| Field | Atlas path | Source | Status as of this writing |
|---|---|---|---|
| County population | `patients` | Census county population estimates | real |
| Diabetes / high-BP / obesity / mental-distress prevalence | `outcomes.*` | CDC PLACES | real |
| Care-access burden | `dom.access` | HRSA HPSA | real |
| HPSA shortage score | `hpsaScore` | HRSA HPSA | real |
| Composite unmet-need index | `needIndex` | derived (SDoH blend) | real |
| Rurality | `rural` | USDA ERS RUCC | real |
| Insurance coverage, age 65+ share | `sdoh.uninsured_rate`, `sdoh.age65_pct` | Census ACS SDoH | **stub** (always null today) |
| Childhood immunization rate | `measures.child_immun` | HRSA UDS | **stub** (constant 50.0 today) |
| Risk-tier distribution | `patientsList[].riskTier` | synthetic patient model | synthetic, not used by this engine (see [Limitations](#limitations)) |
| Historical patient volume, seasonal trends | -- | none | not available; see [Future enhancements](#future-enhancements) |

Asthma prevalence and a cholesterol/lipid measure have no county-level column
in the atlas at all; those two condition drivers always resolve at the config
default (see below). This is a data-source gap, not a bug, and it is why every
prediction reports a confidence level.

## The three-tier fallback

Every input above is resolved in this order, and the tier actually used is
recorded on every prediction (`fallbacks_used`, plus each condition's
`prevalence_tier`):

1. **county** -- the county's own value in `dashboard/data/clinic_atlas.json`
2. **state** -- the mean of that field across every county currently loaded
   (`resource_prediction.state_summary`)
3. **default** -- a fixed value in `resource_planning_config.yml`'s
   `fallback_defaults` / each condition's `default_prevalence_pct`, used only
   when neither of the above is available

Because `sdoh.*` and `measures.*` are stub data for every county today, a
typical prediction resolves those specific inputs at tier 3 -- expected, not
an error, and reflected directly in a lower confidence level.

## Methodology

### 1. Estimated patient volume

```
access_uplift     = min(rural_access_uplift_max, access_burden * rural_access_uplift_per_point)
uninsured_damp    = min(uninsured_dampening_max, uninsured_rate * uninsured_dampening_per_point)
effective_rate    = base_encounters_per_patient_per_30d * (1 + access_uplift) * (1 - uninsured_damp)
estimated_volume  = ceil(county_patients * effective_rate * (window_days / 30))
```

Rounds up: under-planning a clinic's expected volume is worse than
over-planning it, the same convention `supply_needs.py` uses.

### 2. Expected encounters by condition

For each condition driver with a county prevalence input (hypertension,
diabetes, behavioral health, weight-related):

```
annual_cases      = county_patients * (prevalence_pct / 100)
annual_encounters = annual_cases * annual_visits_per_case
window_encounters = ceil(annual_encounters * (window_days / 365))
```

Asthma, hyperlipidemia, and acute/walk-in care have no county prevalence
column, so `prevalence_pct` always resolves at the config default (asthma,
hyperlipidemia) or the driver is a flat per-patient annual rate instead of a
prevalence (acute care).

### 3. Medications, supplies, and equipment

Every item in `resource_planning_config.yml`'s `medications`,
`medical_supplies`, and `diagnostic_equipment` sections names its basis:

| Basis | Formula | Example |
|---|---|---|
| a condition's encounters | `ceil(condition_encounters * factor)` | hypertension medications, test strips |
| the immunization gap | `ceil(patients * (100 - child_immun%) * factor * window/365)` | vaccines |
| total estimated volume | `ceil(estimated_patient_volume * factor)` | gloves, masks, POC testing supplies |
| a condition's window case count | `ceil(window_cases / factor)` | glucose monitors, ECG equipment |
| panel size (durable equipment) | `ceil(patients / factor)` | BP cuffs, pulse oximeters |

Panel-size equipment is a standing on-hand recommendation, not a per-window
consumable count -- it does not change between a 30-day and a 90-day plan.

### 4. Staffing

Reported as a fractional FTE recommendation across the county's primary-care
capacity as a whole, **not rounded up** (unlike consumables, rounding every
fractional FTE up would systematically over-recommend headcount):

```
uplift    = min(uplift_max, driver_value / 100 * uplift_max)   # driver = access burden or need index
effective = patients_per_fte * (1 - uplift)
fte       = patients / effective
```

Behavioral health specialists are the one role driven by a condition caseload
instead of the whole panel: `fte = annual_behavioral_health_cases / cases_per_fte`.

### 5. Priority level

A 0-100 composite, weighted and thresholded entirely in config:

```
score = need_index * w.need_index
      + min(100, hpsa_score / 26 * 100) * w.hpsa_score
      + uninsured_rate * w.uninsured_rate
      + (missing_fields / fields_checked * 100) * w.data_completeness_penalty
```

Thinner data pushes the score up, never down -- a county the engine
understands poorly should be flagged for attention, not quietly treated as low
priority. `score -> Low / Medium / High / Critical` via configured thresholds.

### 6. Confidence level

Counts how many of `confidence.fields_checked` resolved at tier "county" vs.
a fallback. `High` (at most 1 fallback), `Medium` (at most 5), else `Low`, all
configurable.

## Configurability

Every number above lives in `data/reference/resource_planning_config.yml`:
planning windows, utilization and dampening rates, per-condition prevalence
defaults and visit rates, every medication/supply/equipment factor, staffing
ratios, priority weights and thresholds, and confidence cutoffs. Changing any
of it never requires touching `resource_prediction.py`. A caller can also
override any single factor per-prediction via the `overrides` argument
(`predict_resources(..., overrides={"medications.vaccines.doses_per_percent_gap_per_patient": 0.003})`),
the same human-in-the-loop mechanism `supply_needs.py` uses for supply
overrides, without editing the shared config file.

## Reproducing

```
uv run python -c "
import json
from src.model import resource_prediction as rp
records = json.load(open('dashboard/data/clinic_atlas.json'))['records']
cfg = rp.load_config()
ss = rp.state_summary(records, config=cfg)
county = next(r for r in records if r['id'] == '51001')
print(rp.predict_resources(county, 30, config=cfg, state_summary=ss))
"
```

Same inputs always produce the same output -- there is no randomness or
model-fitting step, only arithmetic over disclosed config values.

## Limitations

1. **Not a trained forecast.** No historical utilization time series exists in
   this project's data sources, so there is nothing to validate a predicted
   count against and no error metric to report (contrast with
   `documents/forecast-model-card.md`'s skill/coverage table for the NNDSS
   forecast, which does have history to backtest against).
2. **County-wide, not clinic-specific.** See [scope note](#the-two-things-to-know-first) above.
3. **Prevalence is not the same as diagnosed-and-treated.** CDC PLACES
   prevalence estimates the share of adults with a condition, not the share
   currently engaged in care; encounter counts derived from it are an upper
   bound, not an observed rate.
4. **Two condition drivers (asthma, cholesterol) and two SDoH inputs
   (uninsured rate, age 65+ share) have no live county-level column today** and
   always resolve at the config default. Confidence reflects this; the
   quantities do not silently claim county-specific precision they don't have.
5. **Risk-tier distribution and historical/seasonal volume are listed as
   candidate inputs in the story but are not used by this version.** The
   patient-level risk tier is a synthetic-label model output
   (`documents/modeling.md`), not real utilization, and using it here would
   launder a synthetic signal into an operational quantity. Historical volume
   has no data source at all yet -- see below.
6. **Assumptions are unreviewed.** Every visit-rate, staffing-ratio, and
   per-encounter factor was compiled by the development team from published
   planning benchmarks (CDC, ADA, AHA/ACC, HRSA UDS), not signed off by a
   clinician or a Virginia rural-clinic administrator. `clinical_review:
   pending` is carried on every prediction until that changes.

## Human in the loop

A prediction informs a stocking and staffing conversation; it does not make
one. Every factor is overridable per clinic without touching the shared
config, every quantity rounds toward the safer error (up for consumables,
unrounded for FTE so a whole-number ceiling doesn't overstate headcount), and
every response carries its confidence level, priority factors, and a
plain-language explanation of what drove the numbers so a reviewer can audit
the reasoning, not just the result.

## Future enhancements

Listed in dependency order, from what plugs into the current architecture
first to what requires new data collection:

1. **Historical/seasonal-aware estimation.** `predict_resources` already
   accepts `historical_monthly_volume` and `seasonal_index` keyword arguments
   that scale the base estimate when supplied; nothing calls them yet because
   no historical utilization feed exists. This is the seam a time-series or
   ML model plugs into without changing the function's contract or the API
   response shape.
2. **Real SDoH and UDS-measure data**, replacing the `sdoh.*` / `measures.*`
   stub feeds, would move most predictions from tier 2/3 fallback to tier 1
   and raise confidence levels across the board without any code change.
3. **EHR utilization data** to replace the cross-sectional prevalence x
   visit-rate assumption with observed encounter counts.
4. **Pharmacy inventory system integration**, actual-vs-predicted tracking,
   and periodic retraining once (1)-(3) exist.
5. **Cost estimation, supplier recommendations, and automated procurement
   alerts**, layered on top once the quantity predictions themselves are
   validated against observed consumption.
