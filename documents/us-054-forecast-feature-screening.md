# US-054 Proxy and inequity screening: notifiable-disease forecast

Companion to `us-014-feature-screening.md`, covering the forecasting features in
`src/model/forecast_dataset.py` and the state-to-county allocation in
`src/model/forecast_fairness.py`.

Screened 2026-07-28 against `data/processed/region_condition_history.csv`
(CDC NNDSS, Virginia plus six neighbouring jurisdictions, 2022 W1 to 2026 W28,
237 weeks).

## Scope

The forecast is state-level. There is no county-level model, so there is no
county-level model error to audit. The equity risk sits in two places instead:

1. Which conditions get forecast at all. A condition excluded from the set is a
   clinic need the product cannot warn about.
2. How the state number becomes county numbers. The allocation rule decides who
   gets counted.

## Per-feature verdicts

| Feature | What it is | Verdict | Reasoning |
|---|---|---|---|
| `lag_1` … `lag_4`, `lag_8` | Case counts 1-4 and 8 weeks back | **Keep** | Direct autocorrelation of the target. No demographic content: a case count is not a proxy for who the patient was. |
| `lag_52` | Same week last year | **Keep** | Seasonal term. Carries whatever reporting inequity existed a year ago, which is a data-quality concern rather than an encoded-bias one. |
| `roll_mean_4/8` | Mean of the 4/8 prior weeks | **Keep** | Smoothing only. |
| `roll_std_4/8` | Volatility of prior weeks | **Keep, with a caveat** | Volatility is partly a *reporting* artifact: jurisdictions with thin surveillance staff report in bursts. Retained because it is predictive, but it measures reporting behaviour as well as disease. |
| `woy_sin`, `woy_cos` | Week-of-year cycle | **Keep** | Calendar position. No population content. |

No demographic feature is used. Race, ethnicity, income, insurance status and
ZIP are absent from the forecast model by construction: the input is one
statewide count per condition per week. This is a narrower surface than the
county risk model in `us-014-feature-screening.md`, and deliberately so.

### The borderline case: `roll_std`

Reporting volatility correlates with health-department capacity, which correlates
with the resourcing of the communities a department serves. A jurisdiction that
reports in clumps will show high volatility for reasons that have nothing to do
with disease. Virginia is a single reporting jurisdiction here, so within this
model the term cannot encode between-jurisdiction inequity. If this model is
ever extended to multiple states, `roll_std` must be re-screened, because at
that point it starts encoding which health departments are well funded.

## Condition-selection bias

`FC.FORECAST_CONDITIONS` holds 11 of 139 reported conditions, chosen on observed
volume and reporting continuity. That choice is itself a value judgement.

Volume thresholds favour common conditions: a rare condition that is devastating
for a small population is excluded because it cannot be forecast, not because it
does not matter. The `MIN_HISTORY_WEEKS = 104` threshold favours long-established
reporting, so a newly notifiable condition is invisible until two years have
passed.

Mitigation: excluded conditions surface as `insufficient_history` rather than
being silently absent, and unmapped conditions surface as `unmapped` in
`supply_needs.py`. The gap is visible rather than hidden.

## Allocation fairness, the primary finding

Measured by `src/model/forecast_fairness.py`, which compares each county's
allocated share (population ÷ state population) against an access-weighted
need share (population × access burden ÷ state total).

| Stratum | RUCC | Counties | Population | Allocated share | Need share | Shortfall |
|---|---|---|---|---|---|---|
| metro | 1-3 | 80 | 7,737,548 | 0.8781 | 0.8660 | −0.0122 |
| nonmetro | 4-6 | 20 | 468,766 | 0.0532 | 0.0686 | **+0.0154** |
| rural | 7-9 | 33 | 604,881 | 0.0686 | 0.0655 | −0.0032 |

**Finding: the disparity is in the nonmetro-adjacent stratum, not the most-rural
one.** Nonmetro counties receive 1.5 percentage points less than their
access-weighted need implies, with a mean need ratio of 1.25. The most-rural
stratum tracks its need share closely (−0.003).

This was not the expected result. The initial verdict function checked only the
`rural` stratum and would have reported "no disparity" while the worst-served
group went unexamined. `disparity_verdict()` now evaluates every non-metro
stratum and reports the worst.

Why nonmetro rather than rural: RUCC 4-6 counties in Virginia carry the highest
mean access burden (63.2, against 50.9 for RUCC 7-9). They are populous enough to
be expected to have services and small enough not to, so population share
under-counts their need most sharply.

### Mitigation

- Not corrected in the allocation. Population share stays the rule because it is
  transparent and auditable; substituting an access-weighted allocation would
  bake a modelling judgement into a number the dashboard presents as arithmetic.
- Documented instead. Nonmetro county figures are a floor, not an estimate. This
  is stated in the model card (US-055) and reproduced for the user in the
  early-warning guide.
- Re-run on every build. `uv run python -m src.model.forecast_fairness`
  regenerates the table, so the finding cannot silently go stale as populations
  shift.

## Non-PHI confirmation

Every input is a public aggregate count. No individual-level record enters the
forecast at any stage, consistent with the project's standing non-PHI constraint.

## Open risks

1. Provisional revision. NNDSS weekly counts are revised after publication; the
   ingestion keeps the latest revision, so history changes under the model
   between runs.
2. Reporting gaps read as low counts. Suppressed weeks are held as NULL rather
   than 0, but a *silently* under-reported week is indistinguishable from a
   genuinely quiet one.
3. Single jurisdiction. All conclusions here hold for Virginia only.


---

# Addendum: threat-ranking screening (US-056)

The ranking in `src/model/threat_ranking.py` is a new inference surface and is
screened here on the same terms as the forecast features.

## Inputs

| Input | Verdict | Reasoning |
|---|---|---|
| Recent 8-week mean, Virginia | **Keep** | Observed counts. No demographic content. |
| Seasonal baseline (same weeks, prior 4 years) | **Keep** | Carries prior-year reporting inequity forward, which is a data-quality issue rather than encoded bias. |
| Neighbouring-state ratios | **Keep, with a caveat** | Six jurisdictions with differing surveillance capacity. See below. |
| Volume floor (3 cases/week) | **Keep, documented** | An explicit value judgement, not a neutral filter. See below. |

No demographic variable enters the ranking. The inputs are case counts by
condition, week and jurisdiction.

## The primary concern: reporting effort masquerading as incidence

Ranking by rise means any change in reporting behaviour is indistinguishable
from a change in disease. A jurisdiction that hires an epidemiologist, clears a
backlog, or adopts electronic case reporting will show a rise across many
conditions at once, and this ranking would present that as a threat.

This matters for equity because surveillance capacity tracks health-department
funding, which tracks the resourcing of the communities served. A
well-resourced department makes its population *look* sicker.

Mitigations, none of them complete:

- Regional corroboration helps: a rise in four states is less likely to be one
  department's backlog. It does not help against a *regional* reporting change,
  such as a multi-state reporting-standard update.
- The seasonal baseline absorbs stable differences in reporting effort, since a
  jurisdiction is compared against itself.
- Not corrected. There is no reporting-volume denominator in NNDSS to normalise
  against. It is documented in the model card as the ranking's largest weakness.

## The volume floor is a value judgement

`MIN_RECENT_CASES = 3` keeps a 1-to-4-case jump off the board. It also means a
condition running at 2 cases/week cannot rank however severe it is, which
disadvantages rare high-consequence disease and, by extension, the small
populations such disease tends to concentrate in.

Retained because the alternative, an unfiltered list dominated by single-case
noise, is less useful to a clinic. Recorded here so the trade is visible rather
than implicit.

## Condition selection is no longer a gate

The ranking runs over all 139 reported conditions, which removes the selection
bias documented above for the forecast set: Cyclosporiasis and Measles are
surfaced despite never having been in `FORECAST_CONDITIONS`. What remains is a
guidance gap rather than a visibility gap. A ranked condition without a supply
mapping renders as "no stocking guidance yet" rather than disappearing.

## Blurb provenance

Stocking blurbs were compiled from published CDC guidance by the development
team, not by a clinician. `condition_supply_map.yml` carries
`clinical_review: pending` and the UI renders that state on every threat board.
Removing the flag requires a qualified sign-off, not an edit.
