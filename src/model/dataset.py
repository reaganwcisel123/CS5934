"""Assemble the training frames from the built atlas.

Two frames share this module:
- `county_frame()`  -> real SDoH features, REAL CDC-outcome-derived target.
- `patient_frame()` -> clinical + county-context features, SYNTHETIC label from
  `synthesize_patient_label()` (documented generative model in config.py).

County context for each patient is read from its parent county record (not the
geographic-join `nb` field, which is currently left unmatched upstream).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.catalog import REPO_ROOT
from src.model import config as C

ATLAS_PATH = REPO_ROOT / "dashboard" / "data" / "clinic_atlas.json"


def load_records(path: Path | None = None) -> list[dict]:
    """Load the county records from the built atlas JSON."""
    p = path or ATLAS_PATH
    return json.loads(p.read_text(encoding="utf-8"))["records"]


def county_frame(
    records: list[dict] | None = None,
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """133 counties: real SDoH features -> binary high-preventable-need target."""
    recs = records if records is not None else load_records()
    rows = []

    for record in recs:
        domains = record.get("dom", {})

        rows.append(
            {
                "food": domains.get("food"),
                "access": domains.get("access"),
                # economic/education from real Census ACS (US-013);
                # environment from CDC EJI (US-009).
                "economic": domains.get("economic"),
                "education": domains.get("education"),
                "environment": domains.get("environment"),
                "hpsaScore": record.get("hpsaScore"),
                "rural": record.get("rural"),
                "needIndex": record.get("needIndex"),
                **{
                    outcome: (record.get("outcomes", {}) or {}).get(outcome)
                    for outcome in C.COUNTY_TARGET_OUTCOMES
                },
            }
        )

    required_columns = C.COUNTY_FEATURES + C.COUNTY_TARGET_OUTCOMES
    df = pd.DataFrame(rows).dropna(subset=required_columns)

    # Target: top-tercile chronic-disease burden = z-scored mean of outcomes.
    outcomes = df[C.COUNTY_TARGET_OUTCOMES]
    standardized_outcomes = (
        outcomes - outcomes.mean()
    ) / outcomes.std(ddof=0)

    burden = standardized_outcomes.mean(axis=1)
    target_threshold = burden.quantile(C.COUNTY_TOP_QUANTILE)

    y = (burden >= target_threshold).astype(int)
    y.name = "high_need"

    return (
        df[C.COUNTY_FEATURES].reset_index(drop=True),
        y.reset_index(drop=True),
        C.COUNTY_FEATURES,
    )


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def synthesize_patient_label(
    df: pd.DataFrame,
    seed: int = C.RANDOM_STATE,
) -> np.ndarray:
    """Create the documented synthetic patient-risk label.

    p = sigmoid(logit(prevalence) + signal_strength * z(true drivers) + noise)

    Only a subset of features drives the label, plus noise, so the model has a
    genuine but imperfect learning task. See config.LABEL_DRIVERS.
    """
    rng = np.random.default_rng(seed)

    def standardize(column: str) -> np.ndarray:
        values = df[column].to_numpy(dtype=float)
        standard_deviation = values.std() or 1.0
        return (values - values.mean()) / standard_deviation

    drivers = C.LABEL_DRIVERS

    raw_signal = (
        drivers["z_a1c"] * standardize("a1c")
        + drivers["z_sys"] * standardize("sys")
        + drivers["z_age"] * standardize("age")
        + drivers["access"]
        * (df["ctx_access"].to_numpy(dtype=float) / 100.0)
        + drivers["food"]
        * (df["ctx_food"].to_numpy(dtype=float) / 100.0)
        + drivers["rural"] * df["rural"].to_numpy(dtype=float)
    )

    signal_standard_deviation = raw_signal.std() or 1.0
    signal = (
        raw_signal - raw_signal.mean()
    ) / signal_standard_deviation

    intercept = float(
        np.log(
            C.LABEL_PREVALENCE
            / (1 - C.LABEL_PREVALENCE)
        )
    )

    noise = rng.normal(
        0.0,
        C.LABEL_NOISE_SD,
        size=len(df),
    )

    probabilities = _sigmoid(
        intercept
        + C.LABEL_SIGNAL_STRENGTH * signal
        + noise
    )

    return (
        rng.random(len(df)) < probabilities
    ).astype(int)


def patient_frame(
    records: list[dict] | None = None,
    seed: int = C.RANDOM_STATE,
) -> tuple[pd.DataFrame, pd.Series, list[str], pd.DataFrame]:
    """Build the patient feature frame, target, and aligned county metadata."""
    recs = records if records is not None else load_records()
    rows = []

    for record in recs:
        domains = record.get("dom", {})

        county_context = {
            "ctx_food": domains.get("food"),
            "ctx_access": domains.get("access"),
            "rural": record.get("rural"),
            "needIndex": record.get("needIndex"),
        }

        for patient in record.get("patientsList", []):
            rows.append(
                {
                    "age": patient.get("age"),
                    "sys": patient.get("sys"),
                    "dia": patient.get("dia"),
                    "a1c": patient.get("a1c"),
                    **county_context,
                    "county_fips": record.get("id"),
                    "meta_rural": record.get("rural"),
                }
            )

    # Features and metadata remain in the same DataFrame until incomplete rows
    # are removed. This prevents county metadata from shifting to another patient.
    df = (
        pd.DataFrame(rows)
        .dropna(subset=C.PATIENT_FEATURES)
        .reset_index(drop=True)
    )

    X = df[C.PATIENT_FEATURES].copy()

    metadata = (
        df[["county_fips", "meta_rural"]]
        .rename(columns={"meta_rural": "rural"})
        .reset_index(drop=True)
    )

    y = pd.Series(
        synthesize_patient_label(X, seed),
        name="at_risk",
    )

    return X, y, C.PATIENT_FEATURES, metadata