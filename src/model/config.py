"""Feature lists, the synthetic-label generative model, and training config.

Kept in one place so the model is reproducible and the synthetic target is
auditable (nothing about the patient label is hidden in the training code).
"""

from __future__ import annotations

RANDOM_STATE = 42
TEST_SIZE = 0.25
CV_SPLITS = 5
CV_REPEATS = 5

# --- County model (REAL data) -------------------------------------------------
# Real-variance SDoH only. economic and education are live from the Census ACS
# feed (US-013), and environment is the real CDC EJI Environmental Burden Module
# percentile (US-009), so all three join the model.
COUNTY_FEATURES = [
    "food",
    "access",
    "economic",
    "education",
    "environment",
    "hpsaScore",
    "rural",
    "needIndex",
]

# Target: a county is "high preventable-need" if its chronic-disease burden
# (CDC PLACES) is in the top third. Documented ambulatory-care-sensitive proxy.
COUNTY_TARGET_OUTCOMES = ["diabetes", "bphigh", "obesity"]
COUNTY_TOP_QUANTILE = 2 / 3  # top tercile -> positive

# --- Patient model (SYNTHETIC label) ------------------------------------------
# Features the model trains on: patient clinical signals + their county context.
PATIENT_FEATURES = [
    "age",
    "sys",
    "dia",
    "a1c",
    "ctx_food",
    "ctx_access",
    "rural",
    "needIndex",
]

# Documented generative risk model for the synthetic label. The label is a
# function of only these TRUE drivers (a subset of the features above) plus
# noise, so the classifier has a real learning task and cannot perfectly recover
# it. z_* terms are standardized across the patient population; SDoH terms are
# scaled to 0-1. Tuned to ~20% positive prevalence.
LABEL_PREVALENCE = 0.20
LABEL_SIGNAL_STRENGTH = 1.3
LABEL_NOISE_SD = 0.45

LABEL_DRIVERS = {
    "z_a1c": 0.9,      # higher A1c -> higher risk
    "z_sys": 0.6,      # higher systolic BP -> higher risk
    "z_age": 0.5,      # older -> higher risk
    "access": 1.1,     # worse care-access burden -> higher risk
    "food": 0.7,       # worse food/housing burden -> higher risk
    "rural": 0.6,      # more rural -> higher risk
}

# These quantiles are converted to fixed probability thresholds during training
# and stored with the patient model. Scoring reuses those stored thresholds.
TIER_QUANTILES = {
    "high": 0.80,
    "medium": 0.50,
}

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

# County-level driver labels. needIndex is omitted because it is the SDoH
# composite; the underlying actionable factors are more useful explanations.
COUNTY_DRIVER_LABELS = {
    "access": "Poor care access",
    "food": "Food & housing burden",
    "economic": "Economic hardship",
    "education": "Low educational attainment",
    "environment": "Environmental burden",
    "hpsaScore": "Provider shortage",
    "rural": "Rural isolation",
}