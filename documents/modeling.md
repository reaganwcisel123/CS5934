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
economic and education burdens from the Census ACS feed, the primary-care HPSA score, a
population-based rurality proxy, and the composite need index. The economic and education
domains used to be constant-50 placeholders and were held out of the model. With the Census
key wired (US-013) they now carry real variance across counties, so they join the county
feature list and show up as real drivers of county risk. The environment domain stays out for
now, because its EPA values are still a placeholder until the real EPA feed is wired (US-009).

Patient features: age, systolic and diastolic blood pressure, and A1c on the clinical side,
plus the patient's county context (food burden, care-access burden, rurality, need index)
on the community side. The patient model keeps its existing context features, because its
synthetic label is generated from food, care-access, and rurality (see the targets below).

Feature definitions live in `src/model/config.py` so they stay versioned with the code. One
acceptance item, designing features from the clinic survey, is still open: the survey
responses are not back yet (US-004), so today's features are the public and synthetic
signals we already have.

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

County: logistic regression 0.866 PR-AUC, gradient boosting 0.907, against a 0.338 base rate.
Both jumped once the real economic and education signal entered the model; they were about
0.67 before, when the county model had only five real features.

Patient: logistic regression 0.666 PR-AUC, gradient boosting 0.523, against a 0.267 base
rate. The baseline wins clearly.

We rely on logistic regression for both models. On the patient data gradient boosting does
noticeably worse, so the choice is easy. On the county data gradient boosting now scores a
little higher, but we still keep logistic regression, because the per-county driver story
below needs a linear model and the difference is small. The selection rule keeps logistic
regression whenever it stays within a wider margin on the county target, in
`src/model/train.py`. The simpler model is far easier to explain, which is the whole point of
the "why" for a clinic user. This is the familiar "keep it simple until the data clearly
justifies more" result, and it falls out the same way every run because the split is seeded.

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

The county model used to show a real gap. It scored about 0.78 PR-AUC on less-rural counties
and only 0.54 on more-rural ones, which is the wrong direction for a rural-health tool. We had
tried to fix that by refitting with the two rurality groups weighted equally, and it did not
help, because reweighting cannot invent signal that thin data does not carry.

Adding the real Census economic and education features (US-013) is what actually closed the
gap. The county model now scores about 0.88 PR-AUC on more-rural counties and 0.91 on
less-rural ones, so the two strata are close and the model is no longer markedly worse on the
rural side. This is the outcome we predicted in the earlier write-up: the honest fix was more
real rural signal, not a reweighting trick on thin data. The patient model stays roughly even
across strata (about 0.71 versus 0.65). The remaining gap is small, and we will keep watching
it as the environment feature (US-009) and the clinic survey (US-004) come online.

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
