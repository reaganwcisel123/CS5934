"""Feature lists, the synthetic-label generative model, and training config.

Kept in one place so the model is reproducible and the synthetic target is
auditable (nothing about the patient label is hidden in the training code).
"""

from __future__ import annotations

RANDOM_STATE = 42
TEST_SIZE = 0.25

# --- County model (REAL data) -------------------------------------------------
# Real-variance SDoH only. environment is now the real CDC EJI Environmental
# Burden Module percentile (US-009), so it joins the model. economic and
# education stay out until the Census feed is wired (US-013).
COUNTY_FEATURES = ["food", "access", "environment", "hpsaScore", "rural", "needIndex"]
# Target: a county is "high preventable-need" if its chronic-disease burden
# (CDC PLACES) is in the top third. Documented ambulatory-care-sensitive proxy.
COUNTY_TARGET_OUTCOMES = ["diabetes", "bphigh", "obesity"]
COUNTY_TOP_QUANTILE = 2 / 3  # top tercile -> positive

# --- Patient model (SYNTHETIC label) ------------------------------------------
# Features the model trains on: patient clinical signals + their county context.
PATIENT_FEATURES = ["age", "sys", "dia", "a1c", "ctx_food", "ctx_access", "rural", "needIndex"]

# Documented generative risk model for the synthetic label. The label is a
# function of only these TRUE drivers (a subset of the features above) plus
# noise, so the classifier has a real learning task and cannot perfectly recover
# it. z_* terms are standardized across the patient population; SDoH terms are
# scaled to 0-1. Tuned to ~20% positive prevalence.
LABEL_PREVALENCE = 0.20        # target share of at-risk patients
LABEL_SIGNAL_STRENGTH = 1.3    # how separable the true signal is (higher = easier)
LABEL_NOISE_SD = 0.45          # gaussian noise on the linear predictor
LABEL_DRIVERS = {
    "z_a1c": 0.9,      # higher A1c -> higher risk (diabetes control)
    "z_sys": 0.6,      # higher systolic BP -> higher risk
    "z_age": 0.5,      # older -> higher risk
    "access": 1.1,     # worse care-access burden (0-1) -> higher risk
    "food": 0.7,       # worse food/housing burden (0-1) -> higher risk
    "rural": 0.6,      # more rural (0-1) -> higher risk
}

# Risk tiers by percentile of scored risk (relative prioritization pyramid):
# top 20% = High, next 30% = Medium, bottom 50% = Low.
TIER_QUANTILES = {"high": 0.80, "medium": 0.50}

# Human-readable driver labels for per-patient explainability (US-020).
DRIVER_LABELS = {
    "a1c": "Elevated A1c",
    "sys": "High blood pressure",
    "dia": "High blood pressure",
    "age": "Older age",
    "ctx_food": "Food & housing burden",
    "ctx_access": "Poor care access",
    "rural": "Rural isolation",
    "needIndex": "High community need",
}

# County-level driver labels (why a county is high-risk). needIndex is left out
# on purpose: it is the SDoH composite, so it would just restate the risk rather
# than explain it. We show the underlying, actionable SDoH factors instead.
COUNTY_DRIVER_LABELS = {
    "access": "Poor care access",
    "food": "Food & housing burden",
    "environment": "Environmental burden",
    "hpsaScore": "Provider shortage",
    "rural": "Rural isolation",
}
