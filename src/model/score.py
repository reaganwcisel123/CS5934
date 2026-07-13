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


def load_patient_model():
    """Return the trained patient model, or None if it hasn't been trained yet."""
    if not MODEL_PATH.exists():
        return None
    import joblib
    return joblib.load(MODEL_PATH)


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


def _top_drivers(contribs: np.ndarray, feats: list[str], k: int = 2) -> list[str]:
    labels: list[str] = []
    for j in np.argsort(contribs)[::-1]:
        if contribs[j] <= 0:
            break
        label = C.DRIVER_LABELS.get(feats[j], feats[j])
        if label not in labels:
            labels.append(label)
        if len(labels) >= k:
            break
    return labels


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
        pt["riskDrivers"] = _top_drivers(drivers(Xnp[i]), feats) if drivers else []
    return len(refs)


def main() -> int:
    model = load_patient_model()
    if model is None:
        print("No trained model found -- run `python -m src.model.train` first.")
        return 1
    data = json.loads(ATLAS_PATH.read_text(encoding="utf-8"))
    n = score_records(data["records"], model)
    ATLAS_PATH.write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Scored {n} patients into {ATLAS_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
