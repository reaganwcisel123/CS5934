"""Train + evaluate risk classifiers: baseline vs advanced, with rurality fairness.

    python -m src.model.train --target both      # county + patient
    python -m src.model.train --target patient

Fits a scaled logistic-regression baseline (US-015) AND a gradient-boosting model
(US-016), compares them on PR-AUC + calibration (US-017), and reports a
rurality-stratified fairness slice (US-018). Saves the best model + full metrics
to models/.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow both `python -m src.model.train` and `python src/model/train.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
from sklearn.base import clone  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.utils.class_weight import compute_sample_weight  # noqa: E402

from src.catalog import REPO_ROOT  # noqa: E402
from src.model import config as C  # noqa: E402
from src.model import dataset  # noqa: E402

MODELS_DIR = REPO_ROOT / "models"


def _build(target: str):
    if target == "county":
        X, y, feats = dataset.county_frame()
    elif target == "patient":
        X, y, feats, _ = dataset.patient_frame()
    else:
        raise ValueError(f"unknown target: {target}")
    return X, y, feats


def _make_models() -> dict:
    """Baseline (US-015) + advanced (US-016). Both handle class imbalance."""
    return {
        "logreg": make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000, class_weight="balanced", random_state=C.RANDOM_STATE)),
        "gboost": HistGradientBoostingClassifier(random_state=C.RANDOM_STATE),
    }


def _fit(name: str, model, Xtr, ytr):
    # Tree model has no class_weight param, so pass balanced sample weights.
    if name == "gboost":
        model.fit(Xtr, ytr, sample_weight=compute_sample_weight("balanced", ytr))
    else:
        model.fit(Xtr, ytr)
    return model


def _score(yte, proba) -> dict:
    return {
        "pr_auc": round(float(average_precision_score(yte, proba)), 3),
        "roc_auc": round(float(roc_auc_score(yte, proba)), 3),
        "brier": round(float(brier_score_loss(yte, proba)), 3),
    }


def fairness_by_rurality(proba, yte, rural) -> dict:
    """PR-AUC + positive rate for the test set split at its median rurality.

    Rurality is a primary fairness axis for this project: we check the model
    performs comparably for more-rural vs less-rural counties.
    """
    rural = np.asarray(rural, dtype=float)
    yte = np.asarray(yte)
    proba = np.asarray(proba)
    thr = float(np.median(rural))
    out = {"threshold": round(thr, 3), "strata": {}}
    for label, mask in (("more_rural", rural >= thr), ("less_rural", rural < thr)):
        yy, pp = yte[mask], proba[mask]
        both_classes = len(set(yy.tolist())) == 2
        out["strata"][label] = {
            "n": int(mask.sum()),
            "positive_rate": round(float(yy.mean()) if len(yy) else 0.0, 3),
            "pr_auc": round(float(average_precision_score(yy, pp)), 3) if both_classes else None,
        }
    return out


def _rurality_mitigation(model, name, Xtr, ytr, Xte, yte) -> dict:
    """Refit the best model weighting the two rurality strata equally, then
    re-measure the fairness gap. An honest attempt to shrink any disparity we found.
    """
    thr = float(np.median(Xtr["rural"].to_numpy()))
    grp = (Xtr["rural"].to_numpy() >= thr).astype(int)
    weights = compute_sample_weight("balanced", grp)
    m = clone(model)
    if name == "logreg":
        m.fit(Xtr, ytr, logisticregression__sample_weight=weights)
    else:
        m.fit(Xtr, ytr, sample_weight=weights)
    return fairness_by_rurality(m.predict_proba(Xte)[:, 1], yte, Xte["rural"].to_numpy())


def train_one(target: str) -> dict:
    """Fit both models, compare, pick the best, add a fairness slice, persist."""
    X, y, feats = _build(target)
    base = float(y.mean())
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=C.TEST_SIZE, random_state=C.RANDOM_STATE, stratify=y)

    fitted, results, probas = {}, {}, {}
    for name, model in _make_models().items():
        _fit(name, model, Xtr, ytr)
        fitted[name] = model
        probas[name] = model.predict_proba(Xte)[:, 1]
        results[name] = _score(yte, probas[name])

    best = max(results, key=lambda k: results[k]["pr_auc"])
    # Prefer the linear model when it is within a small margin of the best, so
    # per-item drivers stay faithful (US-020). On this data the two are basically
    # tied, so this keeps explainability at no real accuracy cost.
    if results["logreg"]["pr_auc"] >= results[best]["pr_auc"] - 0.02:
        best = "logreg"
    fair = fairness_by_rurality(probas[best], yte, Xte["rural"].to_numpy())
    mitigated = _rurality_mitigation(fitted[best], best, Xtr, ytr, Xte, yte)
    metrics = {
        "target": target, "n_total": int(len(X)), "n_test": int(len(Xte)),
        "features": feats, "positive_rate": round(base, 3),
        "models": results, "best_model": best,
        "fairness_by_rurality": fair, "fairness_after_mitigation": mitigated,
    }

    MODELS_DIR.mkdir(exist_ok=True)
    import joblib
    joblib.dump(fitted[best], MODELS_DIR / f"{target}_model.joblib")
    (MODELS_DIR / f"{target}_metrics.json").write_text(json.dumps(metrics, indent=2))
    _report(metrics)
    return metrics


def _report(m: dict) -> None:
    print(f"\n=== {m['target']} model ===")
    print(f"  rows={m['n_total']}  test={m['n_test']}  features={len(m['features'])}  base_rate={m['positive_rate']:.3f}")
    print(f"  {'model':8}{'PR-AUC':>9}{'ROC-AUC':>9}{'Brier':>8}")
    for name, r in m["models"].items():
        star = "  <- best" if name == m["best_model"] else ""
        print(f"  {name:8}{r['pr_auc']:>9.3f}{r['roc_auc']:>9.3f}{r['brier']:>8.3f}{star}")
    def _fair(title, f):
        print(f"  {title} (split at rural={f['threshold']}):")
        for lab, s in f["strata"].items():
            pa = f"{s['pr_auc']:.3f}" if s["pr_auc"] is not None else "n/a"
            print(f"    {lab:11} n={s['n']:>3}  pos_rate={s['positive_rate']:.3f}  PR-AUC={pa}")

    _fair("rurality fairness (best model)", m["fairness_by_rurality"])
    _fair("after rurality-balanced retrain", m["fairness_after_mitigation"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["county", "patient", "both"], default="both")
    args = ap.parse_args()
    for t in (["county", "patient"] if args.target == "both" else [args.target]):
        train_one(t)
    print(f"\nSaved best models + full metrics to {MODELS_DIR.relative_to(REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
