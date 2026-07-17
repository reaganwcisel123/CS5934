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


def county_frame(records: list[dict] | None = None) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """133 counties: real SDoH features -> binary high-preventable-need target."""
    recs = records if records is not None else load_records()
    rows = []
    for r in recs:
        dom = r.get("dom", {})
        rows.append({
            "food": dom.get("food"),
            "access": dom.get("access"),
            # environment is now the real CDC EJI burden percentile (US-009).
            "environment": dom.get("environment"),
            "hpsaScore": r.get("hpsaScore"),
            "rural": r.get("rural"),
            "needIndex": r.get("needIndex"),
            **{o: (r.get("outcomes", {}) or {}).get(o) for o in C.COUNTY_TARGET_OUTCOMES},
        })
    df = pd.DataFrame(rows).dropna(subset=C.COUNTY_FEATURES + C.COUNTY_TARGET_OUTCOMES)

    # Target: top-tercile chronic-disease burden = z-scored mean of the outcomes.
    z = (df[C.COUNTY_TARGET_OUTCOMES] - df[C.COUNTY_TARGET_OUTCOMES].mean()) / df[C.COUNTY_TARGET_OUTCOMES].std(ddof=0)
    burden = z.mean(axis=1)
    y = (burden >= burden.quantile(C.COUNTY_TOP_QUANTILE)).astype(int)
    y.name = "high_need"
    return df[C.COUNTY_FEATURES].reset_index(drop=True), y.reset_index(drop=True), C.COUNTY_FEATURES


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def synthesize_patient_label(df: pd.DataFrame, seed: int = C.RANDOM_STATE) -> np.ndarray:
    """Documented synthetic risk label.

    p = sigmoid(logit(prevalence) + signal_strength * z(true drivers) + noise);
    label ~ Bernoulli(p). Only a subset of features drive it (+ noise), so a
    classifier has a genuine, imperfect learning task. See config.LABEL_DRIVERS.
    """
    rng = np.random.default_rng(seed)

    def z(col: str) -> np.ndarray:
        v = df[col].to_numpy(dtype=float)
        s = v.std() or 1.0
        return (v - v.mean()) / s

    d = C.LABEL_DRIVERS
    raw = (
        d["z_a1c"] * z("a1c")
        + d["z_sys"] * z("sys")
        + d["z_age"] * z("age")
        + d["access"] * (df["ctx_access"].to_numpy(dtype=float) / 100.0)
        + d["food"] * (df["ctx_food"].to_numpy(dtype=float) / 100.0)
        + d["rural"] * df["rural"].to_numpy(dtype=float)
    )
    # Center + scale the true signal, then place it around the target prevalence.
    signal = (raw - raw.mean()) / (raw.std() or 1.0)
    intercept = float(np.log(C.LABEL_PREVALENCE / (1 - C.LABEL_PREVALENCE)))
    noise = rng.normal(0.0, C.LABEL_NOISE_SD, size=len(df))
    p = _sigmoid(intercept + C.LABEL_SIGNAL_STRENGTH * signal + noise)
    return (rng.random(len(df)) < p).astype(int)


def patient_frame(
    records: list[dict] | None = None, seed: int = C.RANDOM_STATE
) -> tuple[pd.DataFrame, pd.Series, list[str], pd.DataFrame]:
    """~465 synthetic patients: clinical + county context -> synthetic risk label."""
    recs = records if records is not None else load_records()
    rows, meta = [], []
    for r in recs:
        dom = r.get("dom", {})
        ctx = {
            "ctx_food": dom.get("food"),
            "ctx_access": dom.get("access"),
            "rural": r.get("rural"),
            "needIndex": r.get("needIndex"),
        }
        for pt in r.get("patientsList", []):
            rows.append({
                "age": pt.get("age"), "sys": pt.get("sys"),
                "dia": pt.get("dia"), "a1c": pt.get("a1c"), **ctx,
            })
            meta.append({"county_fips": r.get("id"), "rural": r.get("rural")})

    df = pd.DataFrame(rows).dropna(subset=C.PATIENT_FEATURES).reset_index(drop=True)
    meta_df = pd.DataFrame(meta).loc[df.index].reset_index(drop=True)
    y = pd.Series(synthesize_patient_label(df, seed), name="at_risk")
    return df[C.PATIENT_FEATURES], y, C.PATIENT_FEATURES, meta_df
