"""Score patients with the trained model -> risk + tier + drivers, into the atlas.

    python -m src.model.score          # enrich dashboard/data/clinic_atlas.json in place

Adds to each patient: `risk` (probability), `riskTier` (High/Medium/Low, by
percentile), and `riskDrivers` (top contributing factors -- the "why", US-020).
Requires a trained model (run `python -m src.model.train` first).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.catalog import REPO_ROOT  # noqa: E402
from src.model import config as C  # noqa: E402

ATLAS_PATH = REPO_ROOT / "dashboard" / "data" / "clinic_atlas.json"
MODEL_PATH = REPO_ROOT / "models" / "patient_model.joblib"
COUNTY_MODEL_PATH = REPO_ROOT / "models" / "county_model.joblib"


def load_patient_model():
    """Return the trained patient model, or None if it hasn't been trained yet."""
    if not MODEL_PATH.exists():
        return None
    import joblib
    return joblib.load(MODEL_PATH)


def load_county_model():
    """Return the trained county model, or None if it hasn't been trained yet."""
    if not COUNTY_MODEL_PATH.exists():
        return None
    import joblib
    return joblib.load(COUNTY_MODEL_PATH)


def score_counties(records: list[dict], model) -> int:
    """Attach `modelRisk` + `modelRiskDrivers` (the why) to each county in place."""
    feats = C.COUNTY_FEATURES
    rows, refs = [], []
    for r in records:
        dom = r.get("dom", {})
        feat = {"food": dom.get("food"), "access": dom.get("access"),
                "hpsaScore": r.get("hpsaScore"), "rural": r.get("rural"),
                "needIndex": r.get("needIndex")}
        if any(feat[k] is None for k in feats):
            continue
        rows.append([feat[k] for k in feats])
        refs.append(r)
    if not rows:
        return 0
    X = pd.DataFrame(rows, columns=feats)  # named columns -> no sklearn warning
    Xnp = X.to_numpy(dtype=float)
    proba = model.predict_proba(X)[:, 1]
    drivers = _driver_fn(model)  # non-None only for the linear model
    for i, r in enumerate(refs):
        r["modelRisk"] = round(float(proba[i]), 3)
        r["modelRiskDrivers"] = _top_drivers(drivers(Xnp[i]), feats, C.COUNTY_DRIVER_LABELS) if drivers else []
    return len(refs)


def _driver_fn(model):
    """A per-patient contribution function for a logistic-regression pipeline.

    contribution_i = coef_i * standardized(feature_i); positive => pushes risk up.
    Returns None for non-linear models (per-patient drivers need a linear model).
    """
    steps = getattr(model, "named_steps", {})
    if "logisticregression" not in steps or "standardscaler" not in steps:
        return None
    coef = steps["logisticregression"].coef_[0]
    mean = steps["standardscaler"].mean_
    scale = steps["standardscaler"].scale_
    return lambda x: coef * ((np.asarray(x, dtype=float) - mean) / scale)


def _top_drivers(contribs: np.ndarray, feats: list[str], labels: dict, k: int = 2) -> list[str]:
    out: list[str] = []
    for j in np.argsort(contribs)[::-1]:
        if contribs[j] <= 0:
            break
        label = labels.get(feats[j])
        if label is None or label in out:  # skip unmapped (e.g. needIndex) + dups
            continue
        out.append(label)
        if len(out) >= k:
            break
    return out


def score_records(records: list[dict], model) -> int:
    """Attach risk/riskTier/riskDrivers to each patient in place. Returns count."""
    feats = C.PATIENT_FEATURES
    rows, refs = [], []
    for r in records:
        dom = r.get("dom", {})
        ctx = {"ctx_food": dom.get("food"), "ctx_access": dom.get("access"),
               "rural": r.get("rural"), "needIndex": r.get("needIndex")}
        for pt in r.get("patientsList", []):
            feat = {"age": pt.get("age"), "sys": pt.get("sys"),
                    "dia": pt.get("dia"), "a1c": pt.get("a1c"), **ctx}
            if any(feat[k] is None for k in feats):
                continue
            rows.append([feat[k] for k in feats])
            refs.append(pt)
    if not rows:
        return 0

    X = pd.DataFrame(rows, columns=feats)  # named columns -> no sklearn warning
    Xnp = X.to_numpy(dtype=float)
    proba = model.predict_proba(X)[:, 1]
    hi = float(np.quantile(proba, C.TIER_QUANTILES["high"]))
    md = float(np.quantile(proba, C.TIER_QUANTILES["medium"]))
    drivers = _driver_fn(model)

    for i, pt in enumerate(refs):
        p = float(proba[i])
        pt["risk"] = round(p, 3)
        pt["riskTier"] = "High" if p >= hi else ("Medium" if p >= md else "Low")
        pt["riskDrivers"] = _top_drivers(drivers(Xnp[i]), feats, C.DRIVER_LABELS) if drivers else []
    return len(refs)


def main() -> int:
    pmodel, cmodel = load_patient_model(), load_county_model()
    if pmodel is None and cmodel is None:
        print("No trained models found -- run `python -m src.model.train` first.")
        return 1
    data = json.loads(ATLAS_PATH.read_text(encoding="utf-8"))
    n = score_records(data["records"], pmodel) if pmodel else 0
    m = score_counties(data["records"], cmodel) if cmodel else 0
    ATLAS_PATH.write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Scored {n} patients + {m} counties into {ATLAS_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
