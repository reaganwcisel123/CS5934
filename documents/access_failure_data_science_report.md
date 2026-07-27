# Clinic Needs Atlas: Rural Care Access Failure Model

**Report date:** July 27, 2026  
**Model version:** `access-failure-v1`  
**Repository context:** CS5934 Clinic Needs Atlas  
**Source release:** County Health Rankings & Roadmaps 2025 Annual Data Release supplemental analytic CSV, March 25, 2026

## Executive Summary

This model is a county planning tool. It estimates which counties are likely to be in the highest national quarter of observed preventable hospital stays, using public measures related to insurance coverage, provider availability, and broadband access. It puts an additional access-focused signal into the Clinic Needs Atlas; it is not a clinical prediction for a person and it does not prove that an access barrier caused a hospital stay.

The final training frame contained 3,065 eligible U.S. counties and county equivalents. The selected logistic-regression model had holdout PR-AUC 0.377, ROC-AUC 0.663, Brier score 0.229, and positive-class recall 0.547. The dashboard contains predictions for 130 of 133 Virginia atlas records. The three without predictions are deliberately shown as unavailable.

Preventable hospital stays are used as a public county-level planning indicator, but the reported measure is an age-adjusted rate per 100,000 Medicare fee-for-service enrollees. It should not be read as a result for every resident, a diagnosis, or evidence of causation.

## 1. Problem Definition

The established county need model uses Virginia social determinants of health and CDC chronic-disease outcomes. The separate patient model uses synthetic patient records and a synthetic label. This access-failure model is different: it trains nationally on an observed county outcome, preventable hospital stays, and produces county-level risk probabilities for the Virginia atlas.

The planning question is: *which counties warrant additional local review because their public access-barrier profile resembles counties with unusually high preventable utilization?* The result can help focus outreach, capacity review, and local data collection. It cannot determine why utilization occurred, whether a specific patient needs care, or whether an intervention changed an outcome.

## 2. Data Provenance

**Publisher:** County Health Rankings & Roadmaps / University of Wisconsin Population Health Institute.  
**Dataset:** County Health Rankings & Roadmaps National County Analytic Data.  
**Official file:** [2025 Annual Data Release supplemental analytic CSV, March 25, 2026](https://www.countyhealthrankings.org/sites/default/files/media/document/analytic_supplement_20260325%5B1%5D.csv).  
**Documentation:** [County Health Rankings & Roadmaps data documentation](https://www.countyhealthrankings.org/health-data/methodology-and-sources/data-documentation).  
**Catalog verification date:** July 27, 2026.  
**Geography:** U.S. counties and county equivalents, identified by county FIPS.  
**Raw format:** CSV.

The inspected raw file had 3,204 rows and 554 columns. It included national/state aggregate rows as well as county rows. The source release is 2026; the configured source notes that preventable hospital stays and uninsured adults use 2023 measurement data, while provider and broadband measures have source-specific vintages.

### Official-to-Internal Field Mapping

| Official field | Official meaning | Internal field | Unit | Used as |
| --- | --- | --- | --- | --- |
| `fipscode` | Geographic identifier | `county_fips` | Five-digit FIPS | Join key and prediction key |
| `v005_rawvalue` | Preventable hospital stays | `preventable_hospital_stays` | Age-adjusted rate per 100,000 Medicare fee-for-service enrollees | Outcome |
| `v003_rawvalue` | Uninsured adults | `uninsured_percent` | Percent | Predictor |
| `v004_rawalternatevalue` | Primary-care physician population-to-provider ratio | `primary_care_physician_burden` | Population per provider | Predictor |
| `v062_rawalternatevalue` | Mental-health provider population-to-provider ratio | `mental_health_provider_burden` | Population per provider | Predictor |
| `v131_rawalternatevalue` | Other primary-care provider population-to-provider ratio | `other_primary_care_provider_burden` | Population per provider | Predictor |
| `v166_rawvalue` | Broadband access | `broadband_access_percent` | Percent | Input to engineered predictor |

## 3. Extraction and Cleaning

The adapter reads the official CSV as strings first. This prevents automatic conversion from losing FIPS leading zeros or masking suppression markers. It selects only the field mapping above, retains source-release metadata, and does not treat the full file as an atlas source during a standard dashboard build.

Cleaning steps were:

1. Normalize FIPS values to five digits. Numeric values such as `1001.0` become `01001`.
2. Remove national and state summaries, identified by valid FIPS ending in `000`.
3. Retain valid county equivalents, including Virginia independent cities.
4. Treat blank, `NA`, `N/A`, `Suppressed`, `*`, nonfinite, and similar markers as missing values.
5. Parse percentages expressed as either proportions (for example, `0.81`) or percentages (`81%`) onto a 0-100 scale.
6. Parse provider ratios such as `1,230:1` or `1230` as population-per-provider burdens. A reported zero provider ratio remains missing rather than becoming an arbitrary extreme value.
7. Sort duplicated FIPS deterministically by available field count and original order, then retain the most complete first row.
8. Exclude only counties without the observed target from model eligibility. Predictor missingness is preserved for pipeline imputation.

### Cleaning Results

| Check | Actual result |
| --- | ---: |
| Raw rows | 3,204 |
| Raw columns | 554 |
| Raw rows missing FIPS | 0 |
| Aggregate rows removed | 52 |
| Retained unique counties / equivalents | 3,152 |
| Duplicate FIPS after cleaning | 0 |
| Retained Virginia counties / equivalents | 133 |
| Counties with observed target eligible for modeling | 3,065 |
| Virginia counties with target and prediction | 130 |

### Missingness After County Cleaning

| Field | Missing counties | Missing percent of 3,152 retained |
| --- | ---: | ---: |
| Preventable hospital stays | 87 | 2.760% |
| Uninsured adults | 9 | 0.286% |
| Primary-care physician burden | 263 | 8.344% |
| Mental-health provider burden | 206 | 6.536% |
| Other primary-care provider burden | 88 | 2.792% |
| Broadband access | 8 | 0.254% |

## 4. Data Integration

FIPS, rather than county names, is the join key because county names vary and Virginia has independent cities that behave as county equivalents. The national source is used to train and score; only FIPS-keyed Virginia predictions are attached to the existing atlas records after training.

| Join stage | Population | Matched / retained | Notes |
| --- | ---: | ---: | --- |
| Clean official county source | 3,152 | 3,152 | National training-source coverage |
| Target-eligible national source | 3,065 | 3,065 | Used for model frame |
| Existing Virginia atlas | 133 | 133 | Existing county spine unchanged |
| Virginia prediction attachment | 133 | 130 | Three target-missing counties remain unscored |

No atlas county record is removed when there is no prediction. The additive `accessFailureRisk` object is absent, which the interface renders as **Not available**.

## 5. Data Preparation and Leakage Prevention

The model uses five predictors. `broadband_gap` is engineered as:

```text
broadband_gap = 100 - broadband_access_percent
```

This makes a larger number consistently mean a larger access burden. The continuous outcome, its binary label, threshold helpers, identifiers, and source-year metadata are not in the feature matrix. `src/model/dataset.py` uses an explicit allowlist and raises an error if a prohibited target field appears among predictors.

The eligible dataset is split with `train_test_split`, random seed 42, a 75% / 25% split, and stratification on the binary label. Missing predictors remain missing until `SimpleImputer(strategy="median")` runs inside each candidate pipeline. That means imputation statistics are learned from the training folds, rather than from the full data before a split. Logistic regression also standardizes predictors inside its pipeline.

## 6. Target Definition

The original outcome is the continuous preventable-hospital-stays rate. The binary target is `high_access_failure = 1` when the observed rate is at or above the 75th percentile of eligible national counties.

| Target detail | Actual value |
| --- | ---: |
| Eligible counties | 3,065 |
| National 75th-percentile threshold | 3,510.0 preventable stays per 100,000 |
| Positive counties | 767 |
| Negative counties | 2,298 |
| Positive prevalence | 25.0245% |

The percentile threshold is calculated from the **full eligible national dataset before the split**. This gives a stable, nationally interpretable label for this MVP, but it is a design choice to revisit in temporal validation. It is not a predictor and therefore is not feature leakage, but it means label definition sees held-out outcome distribution.

## 7. Class Balance and Weighting Decisions

The data are not described as "balanced." About one quarter of counties are positive, so the outcome is moderately imbalanced.

| Split | Positive | Negative | Positive percent |
| --- | ---: | ---: | ---: |
| Full eligible frame | 767 | 2,298 | 25.0245% |
| Training set | 575 | 1,723 | 25.0218% |
| Held-out test set | 192 | 575 | 25.0326% |

No under-sampling, over-sampling, or synthetic oversampling was applied. The stratified split preserves the observed class proportion and the held-out test set remains untouched. The logistic-regression candidate uses `class_weight="balanced"`; the histogram-gradient-boosting candidate receives balanced sample weights during fitting. These are training-loss weights, not row creation or deletion. PR-AUC is emphasized because it focuses on performance for the less common positive class, while ROC-AUC and the Brier score add discrimination and probability-quality views.

## 8. Features

| Feature | Source | Formula / direction | Reason |
| --- | --- | --- | --- |
| `uninsured_percent` | `v003_rawvalue` | Higher percent = greater burden | Insurance coverage barrier |
| `primary_care_physician_burden` | `v004_rawalternatevalue` | Higher population per provider = less capacity | Primary-care availability |
| `mental_health_provider_burden` | `v062_rawalternatevalue` | Higher population per provider = less capacity | Behavioral-health capacity |
| `other_primary_care_provider_burden` | `v131_rawalternatevalue` | Higher population per provider = less capacity | Additional primary-care capacity |
| `broadband_gap` | `v166_rawvalue` | `100 - broadband_access_percent`; higher = worse access | Digital access and telehealth barrier |

The configured file did not consistently provide project-wide rurality or existing atlas need-index inputs for national training. Those variables and the proposed interaction terms were intentionally omitted rather than imputed from a different source.

## 9. Models Tested and Selection

Two actual candidates were trained:

1. **Logistic regression:** median imputation, standard scaling, maximum 1,000 iterations, balanced class weights, and a fixed random seed. It is comparatively interpretable because its coefficients can be converted into local standardized contributions.
2. **Histogram gradient boosting classifier:** median imputation, balanced sample weights, and the same fixed random seed. It can model nonlinear effects but has less direct local explanation.

No dummy baseline was implemented in this model path. Candidate selection uses mean repeated-cross-validation PR-AUC: five folds repeated five times, for 25 folds total. A logistic model is preferred within a 0.02 PR-AUC explainability margin. In this run, logistic regression also had the higher mean PR-AUC, so selection did not require trading performance away for interpretability.

| Model | Mean CV PR-AUC | CV PR-AUC SD | Holdout PR-AUC | Selected |
| --- | ---: | ---: | ---: | --- |
| Logistic regression | 0.364 | 0.022 | 0.377 | Yes |
| Histogram gradient boosting | 0.359 | 0.019 | 0.370 | No |

## 10. Holdout Results

| Model | PR-AUC | ROC-AUC | Brier score | Positive recall | Confusion matrix `[TN, FP] / [FN, TP]` |
| --- | ---: | ---: | ---: | ---: |
| Logistic regression | 0.377 | 0.663 | 0.229 | 0.547 | `[392, 183] / [87, 105]` |
| Histogram gradient boosting | 0.370 | 0.639 | 0.212 | 0.411 | `[422, 153] / [113, 79]` |

PR-AUC summarizes how well higher scores concentrate true high-utilization counties. ROC-AUC measures ranking discrimination across thresholds. The Brier score measures average squared probability error, so lower is better. Recall is the fraction of observed high-access-failure counties identified at the 0.5 classification threshold. The gradient-boosting candidate has a lower Brier score in this particular holdout, but logistic regression has stronger PR-AUC and recall and is the selected transparent model.

The output artifacts do not contain a calibration curve, rural-versus-non-rural performance table, or a geographic holdout analysis. The metrics record `fairness_by_rurality: null` because rurality is not part of this national modeling frame.

## 11. Model Interpretation and Error Analysis

For the selected model, each row is first median-imputed, then standardized with the trained scaler. The implementation multiplies each standardized feature by its fitted logistic coefficient and serializes up to three largest contributions as readable labels such as **Limited broadband access**. These labels identify model-associated predictors for that county; they do not establish a cause or replace local review.

On the held-out set, the selected model produced 183 false positives and 87 false negatives at a 0.5 threshold. A false positive is a county predicted high risk whose observed target was below the national threshold; a false negative is a target-positive county assigned below 0.5. The saved artifacts are sufficient for those aggregate counts but do not retain enough evaluation-row metadata to responsibly report named near-threshold counties or rural subgroup errors. That analysis would need persisted held-out FIPS, outcomes, probabilities, predictor missingness, and a defensible rurality source.

## 12. Atlas Integration and Appropriate Use

Training writes four ignored artifacts under `models/access_failure/`: `model.joblib`, `metrics.json`, `model_card.json`, and `predictions.json`. The last file is FIPS-keyed and contains Virginia predictions only. The second atlas build attaches each valid prediction to the matching existing record and adds compact model metadata at the top level.

The live Access Failure Risk tab uses those generated values to show county counts, risk tiers, median risk, PR-AUC, selected-county prediction details, observed outcome, drivers, source/model year, source citation, methodology, and limitations. Counties can be searched, filtered, sorted, and selected. Missing predictions are explicitly unavailable.

Appropriate uses include prioritizing counties for additional review, identifying access-capacity gaps, planning outreach, comparing existing need with access-risk signals, and deciding where local data collection would be valuable. Inappropriate uses include denying services, diagnosing or triaging a person, claiming program impact, claiming causation, or replacing local subject-matter review.

## 13. Reproducibility

```bash
uv sync --extra model
uv run --env-file .env python src/build_dataset.py --refresh
uv run python -m src.model.train --target access-failure
uv run python src/build_dataset.py
uv run pytest -q
uv run python -m http.server 8000
```

Use [http://localhost:8000/dashboard/clinic-needs-atlas-live.html](http://localhost:8000/dashboard/clinic-needs-atlas-live.html) for the live app. The final dataset build is required because it merges `models/access_failure/predictions.json` and model metadata into the dashboard JSON.

## 14. Limitations

- The unit is a county or county equivalent, not an individual or a clinical encounter.
- The outcome chiefly reflects Medicare fee-for-service beneficiaries, not all residents.
- Source release and measurement years lag current conditions and differ by measure.
- Public data can be suppressed, missing, or measured with error.
- A binary 75th-percentile label discards some detail from the continuous utilization rate.
- The threshold is defined from all eligible counties before splitting, an MVP choice requiring future validation.
- Random county splits can be optimistic when neighboring counties share conditions; no geographic or temporal holdout was used.
- Display tiers (High at 0.67, Medium at 0.33) are communication bands, not clinical thresholds.
- No causal conclusion is supported, and probability calibration needs deeper assessment.

## Conclusion

The model adds a transparent, national public-data access-risk signal to the existing Clinic Needs Atlas. It is useful as a starting point for county planning discussions because it connects insurance, provider, and broadband barriers with an observed county utilization indicator. The first run demonstrates moderate ranking performance and a readable logistic explanation path, while the limitations make clear that the output should guide review, not make decisions on its own. The next evidence-building steps are temporal/geographic validation, calibration assessment, better capacity inputs, and locally governed use of the scores.
