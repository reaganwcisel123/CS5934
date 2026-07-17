# Predictive modeling notes

This covers the two risk models in `src/model/`, how we built them, and what we
found. It backs the modeling and decision-support stories (US-013, US-016 through
US-020). Everything here is reproducible with `./scripts/train-model.sh`.

## Two models, on purpose

We train two models because the project has to answer two different questions.

The county model answers which communities carry the most preventable-hospitalization
burden. It learns from real public data (CDC PLACES chronic-disease rates and the SDoH
domains already in the atlas), so its performance actually means something.

The patient model answers which patients a clinic should reach first. There are no real
patient outcomes to train on, and there never will be, because the project is non-PHI by
design. So the patient label is synthetic, generated from a documented rule (below). The
patient model shows the full who, why, and what-next workflow end to end, but its accuracy
is a statement about the pipeline, not a claim about real people.

## Features (US-013)

We keep clinical and community features separate on purpose, so you can always tell which
kind of signal is driving a result.

County features, all real: the USDA food-access burden, the HRSA care-access burden, the
primary-care HPSA score, a locked rurality measure (see below), and the composite need index.
We left the economic, education, and environment domains out of the model for now because
they are still placeholders (a constant 50) until the Census and EPA keys are wired in.
Once those are live they drop straight into the same feature list.

Patient features: age, systolic and diastolic blood pressure, and A1c on the clinical side,
plus the patient's county context (food burden, care-access burden, rurality, need index)
on the community side.

Feature definitions live in `src/model/config.py` so they stay versioned with the code. One
acceptance item, designing features from the clinic survey, is still open: the survey
responses are not back yet (US-004), so today's features are the public and synthetic
signals we already have.

## Rural population (US-007)

Rurality is a locked measure now, not an informal proxy. We use the USDA Economic Research Service
Rural-Urban Continuum Codes for 2023, which assign every county a code from 1, most urban metro, to 9, most
rural, based on the 2023 OMB metro delineation and 2020 population. We normalize that code to a 0 to 1 rural
score, where RUCC 1 maps to 0.0 and RUCC 9 maps to 1.0, so it enters the model on the same scale the old
value used. The codes for Virginia's 133 counties are committed in `data/reference/va_county_rucc.csv`, the
build reads them in `src/build_dataset.py`, and each county record carries a `ruralityMethod` tag so the
choice is auditable.

This replaces the earlier population-based proxy, one minus the county population percentile, which was a
stand-in rather than a defined rurality classification. Locking the measure means the rural population that
both the model and the fairness analysis rest on is a fixed, published constraint. Switching to it also moved
the numbers: the county model PR-AUC rose from about 0.67 to about 0.80 on its own, because the RUCC code
carries real signal the population share did not.

## The targets

County target: a county is "high preventable-need" if its chronic-disease burden is in the
top third. That burden is the averaged z-score of diabetes, high blood pressure, and obesity
prevalence from CDC PLACES. It is a stand-in for ambulatory-care-sensitive risk. We keep the
SDoH features and the health-outcome target on opposite sides of the model so nothing leaks.

Patient target: a documented generative rule in `src/model/dataset.py`. Each patient's risk
is a logistic function of a few real drivers (A1c, systolic blood pressure, age, care-access
burden, food burden, and rurality) plus noise, tuned to roughly a 20 percent positive rate.
Only some of the features drive the label and there is genuine noise on top, so the model
has a real learning problem and cannot recover the label perfectly. We chose this over the
random flag the old synthetic data used to ship, which no model can learn from, so the
pipeline demonstrates a real signal instead of chance.

## Model comparison and choice (US-016)

For each target we train a logistic-regression baseline and a gradient-boosting model and
compare them on the same held-out split.

County: logistic regression 0.669 PR-AUC, gradient boosting 0.670, against a 0.338 base rate.
They are effectively tied.

Patient: logistic regression 0.660 PR-AUC, gradient boosting 0.471, against a 0.267 base
rate. The baseline wins clearly.

We rely on logistic regression. On a few hundred rows the gradient-boosting model does not
earn its extra complexity, and on the patient data it does noticeably worse. The simpler
model is also far easier to explain, which matters for the driver story below. This is the
familiar "keep it simple until the data justifies more" result, and it falls out the same
way every run because the split is seeded.

## Evaluation (US-017)

PR-AUC is our headline number, not accuracy. The positive class is the minority, so accuracy
would happily reward a model that calls everyone low risk. Both models clear their base rate
by a wide margin (about +0.33 to +0.39).

We report the Brier score as a calibration check. The patient model lands at 0.167 and the
county model near 0.20, which is reasonable for probabilities we then turn into tiers.

We prioritize recall over precision, because a missed high-risk patient is the expensive
error here. The logistic model is fit with balanced class weights so the minority class is
not ignored, and the classification report prints recall per class.

## Fairness across rurality (US-018)

Rurality is a primary analysis for this project, not an afterthought, so we measure
performance separately for more-rural and less-rural counties, split at the median rurality
of the test set.

With rurality now locked to the RUCC measure (US-007), the split itself is defined by a published
classification rather than a population proxy, and the numbers shift. The county model scores about 0.93
PR-AUC on more-rural counties and about 0.57 on less-rural ones, and the patient model about 0.76 versus
0.45. The gap is still sizable, but it now runs in the less-worrying direction for a rural-health tool: the
model ranks rural counties well and is weaker on the more-urban ones, rather than the reverse we saw with the
old proxy. Read these with care, because each stratum is small, about 17 counties per side for the county
split, and the two strata have different positive rates, which PR-AUC is sensitive to.

We still refit the model weighting the two rurality strata equally and report it for transparency, and we
keep watching the gap. Locking the rurality measure was the step US-007 asked for. The next real gains come
from more rural signal: the Census economic and education features under US-013, the EPA environment feature
under US-009, and later the clinic survey, none of which are folded in on this branch yet.

## Risk tiers (US-019)

We turn each patient's probability into a High, Medium, or Low tier by percentile rather than
a fixed cutoff. The top 20 percent of scores are High, the next 30 percent Medium, and the
bottom half Low. We use a percentile pyramid because the tier exists for prioritization: a
clinic wants a short, ranked list of who to reach first, and a pyramid gives a small High
group with a clear ordering under it. The thresholds sit in `src/model/config.py` rather than
buried in the code. The tiers come off the logistic model's probabilities, which the Brier
score above checks for calibration, so a tier reflects model probability and not a raw score.
The at-risk panel sorts by risk so the highest patients show up first.

## Explainability (US-020)

For each flagged patient we surface the top two factors pushing their risk up, in plain
language ("Elevated A1c", "Poor care access", "Food and housing burden", and so on). Because
the patient model is linear, these are the real contributions to that patient's score (the
model coefficient times the standardized feature value), not a story added after the fact.
That keeps the explanation faithful to what the model actually did. The labels are written for
a clinic user with no machine-learning background, and the clinical drivers (A1c, blood
pressure, age) stay distinct from the community drivers (care access, food and housing,
rurality) so a reader can tell them apart.
