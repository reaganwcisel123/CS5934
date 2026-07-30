# Model card — Notifiable-disease early warning (US-050)

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
| Coverage | Virginia, 2022 W1 – 2026 W28 (237 weeks) |
| Granularity | State × condition × MMWR week |
| Conditions forecast | 11 of 139 reported, by volume and reporting continuity |
| PHI | None. Public aggregate counts only |

Suppressed or not-reportable weeks (`N`/`U`/`NC` flags) are held as NULL, never 0.
Provisional weeks are revised upstream; the latest revision wins, so history can
change between runs.

## Model

Per-condition gradient-boosted quantile regression (scikit-learn), one model set
per condition. Features are lags 1–8 and 52, rolling mean/SD over 4 and 8 prior
weeks, and week-of-year as a sine/cosine pair. All features are strictly past;
`forecast_dataset.assert_no_leakage()` fails the build if a lag column is ever
not `target.shift(n)`.

Conditions are modelled separately because they span two orders of magnitude
(Chlamydia ~682/week, Giardiasis ~4/week). Pooling them degraded both error and
interval calibration.

Intervals are **conformalized** (split-CQR): raw quantile regression covered only
60% at a nominal 80%, so the band is widened by the residual quantile measured on
held-out weeks.

## Evaluation

Rolling-origin backtest, 8 conditions with enough contiguous history, 40 fold-fits.
Skill is model error ÷ baseline error, so **below 1.0 means the model wins**.

| Metric | Result |
|---|---|
| Skill vs naive (last week) | **0.91** ± 0.17 — beats naive on 6 of 8 |
| Skill vs seasonal naive | **0.81** ± 0.20 — beats it on 6 of 8 |
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

**Two conditions lose to the naive baseline and should be read as such.**
Chlamydia is the worst (1.28) and also the highest-volume series, so it dominates
raw error totals — its 65% coverage is the weakest interval in the set. For
Chlamydia and Giardiasis, last week's count is a better predictor than this model.

## Fairness

Full analysis in `documents/us-054-forecast-feature-screening.md`.

The forecast is state-level, so there is no county-level error to audit. The
equity risk is in the allocation, measured by comparing each county's population
share against an access-weighted need share:

- **Nonmetro-adjacent counties (RUCC 4–6) are under-allocated by 1.5 percentage
  points**, mean need ratio 1.25. Their figures are a **floor**, not an estimate.
- Most-rural counties (RUCC 7–9) track their need share closely (−0.003).
- The disparity is **not** where it was expected. A rural-only check would have
  reported no disparity and missed the worst-served group.

No demographic feature enters the model. Race, ethnicity, income, insurance and
ZIP are absent by construction — the input is one statewide count per week.

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
