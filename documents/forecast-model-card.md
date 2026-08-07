# Model card: notifiable-disease early warning (US-050)

**Version** 1.0 · **Evaluated** 2026-07-28 · **Code** `src/model/forecast.py`

## The one thing to know first

**County numbers produced by this system are allocated, not observed.** CDC NNDSS
reports at the state level only. Every county figure in the dashboard and API is
Virginia's forecast split by county population share. It shows relative expected
load. It is not a count of cases in that county, and it must never be read as one.

## Intended use

Four-week-ahead planning for a small rural clinic: roughly how much notifiable
disease Virginia is likely to see, and what supplies that implies. It exists to
inform a stocking and staffing decision.

**Not intended for:** diagnosis, individual patient care, outbreak declaration,
public reporting of county case counts, or any clinical decision. This is a
capstone prototype for academic evaluation, not a production clinical tool.

## Data

| | |
|---|---|
| Source | CDC NNDSS Weekly Data (`cdc_nndss`, Socrata `x9gk-5huc`) |
| Coverage | Virginia, 2022 W1 to 2026 W28 (237 weeks) |
| Granularity | State × condition × MMWR week |
| Conditions forecast | 11 of 139 reported, by volume and reporting continuity |
| PHI | None. Public aggregate counts only |

Suppressed or not-reportable weeks (`N`/`U`/`NC` flags) are held as NULL, never 0.
Provisional weeks are revised upstream; the latest revision wins, so history can
change between runs.

## Model

Per-condition gradient-boosted quantile regression (scikit-learn), one model set
per condition. Features are lags 1-4 and 8, the 52-week seasonal lag, rolling
mean/SD over the 4 and 8 prior weeks, and week-of-year as a sine/cosine pair.
All features are strictly past; `forecast_dataset.assert_no_leakage()` fails the
build if a lag column is ever not `target.shift(n)`.

Conditions are modelled separately because they span two orders of magnitude
(Chlamydia ~682/week, Giardiasis ~4/week). Pooling them degraded both error and
interval calibration.

Intervals are conformalized (split-CQR). Raw quantile regression covered only
60% at a nominal 80%, so the band is widened by the residual quantile measured on
held-out weeks.

## Evaluation

Rolling-origin backtest, 8 conditions with enough contiguous history, 40 fold-fits.
Skill is model error ÷ baseline error, so below 1.0 means the model wins.

| Metric | Result |
|---|---|
| Skill vs naive (last week) | **0.91** ± 0.17, beats naive on 6 of 8 |
| Skill vs seasonal naive | **0.81** ± 0.20, beats it on 6 of 8 |
| MAPE | 37.5% ± 16.8 |
| Interval coverage | **81%** ± 7 against a nominal 80% |

### Per condition

| Condition | Skill vs naive | MAE | MAPE | Coverage |
|---|---|---|---|---|
| Campylobacteriosis | 0.68 | 8.8 | 23% | 75% |
| Cryptosporidiosis | 0.76 | 2.4 | 60% | 85% |
| STEC | 0.83 | 2.9 | 47% | 80% |
| Salmonellosis | 0.87 | 5.8 | 28% | 85% |
| Shigellosis | 0.90 | 2.3 | 53% | 80% |
| Gonorrhea | 0.91 | 31.5 | 16% | 90% |
| **Giardiasis** | **1.03** | 2.1 | 54% | 85% |
| **Chlamydia trachomatis** | **1.28** | 104.2 | 19% | 65% |

Two conditions lose to the naive baseline and should be read as such. Chlamydia
is the worst (1.28) and also the highest-volume series, so it dominates raw error
totals; its 65% coverage is the weakest interval in the set. For Chlamydia and
Giardiasis, last week's count is a better predictor than this model.

## Threat ranking (US-056)

A separate inference from the forecast, answering "what is unusual right now"
rather than "how many cases next month". It runs over all 139 reported
conditions, not just the 11 that are forecast.

```
recent        = mean weekly cases over the last 8 reported weeks
seasonal_base = mean over the SAME MMWR weeks in the prior 4 years
ratio         = (recent + 1) / (seasonal_base + 1)
neighbours    = neighbouring states where ratio > 1.2 and recent >= 2
score         = ratio * (1 + 0.10 * neighbours)
```

Filtered to `recent >= 3` cases/week.

**Why the baseline is seasonal.** Against a trailing 26-week window
Cyclosporiasis reads as a 16x rise every July, which is a restatement of the
calendar rather than a finding. Against the same weeks in prior years it is 2.4x,
which is an actual anomaly. The seasonal baseline also moves Measles from
mid-table to a clear first, which is the clinically correct answer.

**Why the +1 smoothing.** Measles has no prior-year reports in 3 of the last 4
years. An unsmoothed ratio divides by ~0 and returns infinity, which would sort
above everything regardless of how few cases it represents.

**Regional corroboration.** Virginia is compared against Maryland, West Virginia,
Kentucky, Tennessee, North Carolina and DC. All seven report through the same
MMWR week, so the comparison is fair. Corroboration separates a real regional
signal from a Virginia reporting artifact, but it cannot separate a regional
*reporting* change from a regional *disease* change.

### Ranking as of 2026 W29

| Condition | Now /wk | Seasonal norm | Ratio | Neighbours |
|---|---|---|---|---|
| Measles, Indigenous | 12.3 | 1.0 | 6.67x | 2 |
| Cyclosporiasis | 16.0 | 6.1 | 2.40x | 4 |
| Giardiasis | 7.9 | 3.5 | 1.96x | 2 |
| Hepatitis C, chronic, Probable | 98.5 | 46.4 | 2.10x | 1 |
| Hepatitis B, chronic, Confirmed | 16.6 | 6.7 | 2.27x | 0 |

### Limitations specific to the ranking

1. **Reporting effort is indistinguishable from incidence.** A health department
   that clears a backlog produces the same signal as an outbreak. This is the
   ranking's biggest weakness and it cannot be corrected from this data alone.
2. **County figures under a threat are an extrapolation, not a forecast.** Most
   ranked conditions are outside the forecast set, so the county number is the
   current observed rate carried forward and allocated by population share. The
   API labels it `projection_basis: observed_rate`.
3. **Four prior years is a thin baseline**, and 2022-2023 reporting was still
   COVID-disrupted for some conditions.
4. **The volume floor hides small but serious conditions.** A condition running
   at 2 cases/week cannot rank, however severe.

## Fairness

Full analysis in `documents/us-054-forecast-feature-screening.md`.

The forecast is state-level, so there is no county-level error to audit. The
equity risk is in the allocation, measured by comparing each county's population
share against an access-weighted need share:

- Nonmetro-adjacent counties (RUCC 4-6) are under-allocated by 1.5 percentage
  points, mean need ratio 1.25. Their figures are a floor, not an estimate.
- Most-rural counties (RUCC 7-9) track their need share closely (−0.003).
- The disparity is not where it was expected. A rural-only check would have
  reported no disparity and missed the worst-served group.

No demographic feature enters the model. Race, ethnicity, income, insurance and
ZIP are absent by construction: the input is one statewide count per week.

## Limitations

1. **State-to-county allocation.** The headline caveat, above.
2. **Two conditions underperform the baseline.** Chlamydia and Giardiasis.
3. **Absence is not safety.** `insufficient_history` means the model cannot
   forecast, not that a condition is quiet. Under-reported weeks are
   indistinguishable from genuinely quiet ones.
4. **Staleness varies by condition.** Series stop reporting at different weeks;
   `weeks_stale` is published per condition and was 13 weeks for Legionellosis at
   evaluation. A stale forecast is not current intelligence.
5. **Provisional data revise.** History changes under the model between runs.
6. **Virginia only.** `roll_std` must be re-screened before any multi-state use,
   since it would begin encoding health-department capacity.
7. **11 of 139 conditions.** A rare but serious condition is excluded because it
   cannot be forecast, not because it does not matter.

## Human in the loop

The forecast informs a stocking decision; it does not make one. Supply quantities
come from a hand-authored, reviewable mapping
(`data/reference/condition_supply_map.yml`), never from the model, and every item
is overridable per clinic. Quantities are ranges from the prediction interval, not
point values.

## Reproducing

```
uv run python -m src.ingestion.cdc_nndss      # refresh the series
uv run python -m src.model.forecast --backtest --train
uv run python -m src.model.forecast_fairness
```
