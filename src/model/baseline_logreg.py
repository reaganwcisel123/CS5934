"""US-015: Interpretable logistic-regression baseline for preventable
hospitalization risk.

Reads the already-built dashboard artifact (dashboard/data/clinic_atlas.json)
rather than re-running the ingestion pipeline, so training doesn't require
network access or a CENSUS_API_KEY -- it's reproducible from a frozen
snapshot of the data. Re-run `python src/build_dataset.py` first if you want
to train against fresh data.

KNOWN CAVEAT (see src/ingestion/synthetic_clinical.py):
`preventable_hospitalization_flag` is currently assigned independently at
random (rng.next() < 0.18), not as a function of any patient or SDoH
feature. Until the synthetic generator encodes a real relationship, this
baseline is expected to perform near the ~18% base rate -- that is itself
a valid, reproducible result establishing the noise floor for later model
comparisons, not a bug in this script.

Run:
    python -m src.models.baseline_logreg
    python -m src.models.baseline_logreg --atlas path/to/clinic_atlas.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from src.catalog import REPO_ROOT

ATLAS_PATH_DEFAULT = REPO_ROOT / "dashboard" / "data" / "clinic_atlas.json"
RESULTS_DIR = REPO_ROOT / "experiments" / "baseline_logreg"

TARGET = "preventable_hospitalization_flag"
NUMERIC_FEATURES = ["age", "sys", "dia", "a1c"]
DOMAIN_FEATURES = ["nb_economic", "nb_education", "nb_food", "nb_environment", "nb_access"]
CATEGORICAL_FEATURES = ["struggleDom"]
# Kept alongside the model, but NOT used as predictors -- reserved for the
# rurality-focused fairness analysis planned later in the project.
SUBGROUP_COLUMNS = ["county_fips", "region", "rural", "needIndex"]

RANDOM_STATE = 42


def load_patient_frame(atlas_path: Path) -> pd.DataFrame:
    """Flatten dashboard/data/clinic_atlas.json's per-county patientsList into
    one row per synthetic patient, with county-level SDoH context attached."""
    atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
    rows = []
    for county in atlas["records"]:
        county_context = {
            "county_fips": county["id"],
            "region": county.get("region"),
            "rural": county.get("rural"),
            "needIndex": county.get("needIndex"),
        }
        for patient in county.get("patientsList", []):
            nb = patient.get("nb", {}) or {}
            row = {
                **county_context,
                "age": patient.get("age"),
                "sys": patient.get("sys"),
                "dia": patient.get("dia"),
                "a1c": patient.get("a1c"),
                "struggleDom": patient.get("struggleDom"),
                "nb_economic": nb.get("economic"),
                "nb_education": nb.get("education"),
                "nb_food": nb.get("food"),
                "nb_environment": nb.get("environment"),
                "nb_access": nb.get("access"),
                TARGET: patient.get(TARGET),
            }
            rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit(f"No patient records found in {atlas_path}")
    return df


def build_feature_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    X = df[NUMERIC_FEATURES + DOMAIN_FEATURES].copy()
    X[NUMERIC_FEATURES] = X[NUMERIC_FEATURES].fillna(X[NUMERIC_FEATURES].median())
    # Domain burden columns use 50.0 (neutral) when entirely missing, matching
    # the same placeholder convention StubSource already uses elsewhere in the
    # pipeline for not-yet-wired sources -- keeps the fallback consistent rather
    # than inventing a new one here.
    X[DOMAIN_FEATURES] = X[DOMAIN_FEATURES].fillna(50.0)
    dummies = pd.get_dummies(df["struggleDom"], prefix="struggle", dummy_na=False)
    X = pd.concat([X, dummies], axis=1)
    y = df[TARGET].astype(int)
    return X, y


def train_baseline(X_train: pd.DataFrame, y_train: pd.Series) -> tuple[LogisticRegression, StandardScaler]:
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_train)
    # class_weight="balanced" because the outcome is heavily imbalanced
    # (see Team_5 project definition: PR-AUC/calibration over raw accuracy).
    model = LogisticRegression(
        class_weight="balanced",
        max_iter=1000,
        C=1.0,
        solver="lbfgs",
        random_state=RANDOM_STATE,
    )
    model.fit(X_scaled, y_train)
    return model, scaler


def evaluate(model: LogisticRegression, scaler: StandardScaler,
             X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    X_scaled = scaler.transform(X_test)
    proba = model.predict_proba(X_scaled)[:, 1]
    preds = model.predict(X_scaled)

    metrics = {
        "n_test": int(len(y_test)),
        "positive_rate_test": round(float(y_test.mean()), 4),
        "roc_auc": round(float(roc_auc_score(y_test, proba)), 4),
        "pr_auc": round(float(average_precision_score(y_test, proba)), 4),
        "brier_score": round(float(brier_score_loss(y_test, proba)), 4),
        "confusion_matrix": confusion_matrix(y_test, preds).tolist(),
        "classification_report": classification_report(y_test, preds, output_dict=True, zero_division=0),
    }
    return metrics


def coefficient_table(model: LogisticRegression, feature_names: list[str]) -> pd.DataFrame:
    """The interpretable part: which features push risk up or down."""
    return (
        pd.DataFrame({"feature": feature_names, "coefficient": model.coef_[0]})
        .assign(odds_ratio=lambda d: d["coefficient"].apply(lambda c: round(2.71828 ** c, 4)))
        .sort_values("coefficient", key=abs, ascending=False)
        .reset_index(drop=True)
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", type=Path, default=ATLAS_PATH_DEFAULT,
                    help="path to clinic_atlas.json (default: dashboard/data/clinic_atlas.json)")
    ap.add_argument("--test-size", type=float, default=0.25)
    args = ap.parse_args()

    if not args.atlas.exists():
        raise SystemExit(
            f"{args.atlas} not found. Run `python src/build_dataset.py` first "
            "to produce the dataset this model trains on."
        )

    df = load_patient_frame(args.atlas)
    X, y = build_feature_matrix(df)

    if y.nunique() < 2:
        raise SystemExit("Target has a single class in this snapshot -- cannot train/evaluate.")

    X_train, X_test, y_train, y_test, df_train, df_test = train_test_split(
        X, y, df, test_size=args.test_size, random_state=RANDOM_STATE, stratify=y
    )

    model, scaler = train_baseline(X_train, y_train)
    metrics = evaluate(model, scaler, X_test, y_test)
    coefs = coefficient_table(model, list(X.columns))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "scaler": scaler, "features": list(X.columns)},
                RESULTS_DIR / "model.joblib")
    (RESULTS_DIR / "metrics.json").write_text(json.dumps({
        "random_state": RANDOM_STATE,
        "n_total_patients": int(len(df)),
        "test_size": args.test_size,
        "features": list(X.columns),
        "subgroup_columns_reserved_for_fairness_analysis": SUBGROUP_COLUMNS,
        "known_caveat": (
            "preventable_hospitalization_flag is currently assigned "
            "independently at random in src/ingestion/synthetic_clinical.py "
            "(rng.next() < 0.18), not as a function of any feature. Metrics "
            "below reflect that noise floor, not real predictive signal."
        ),
        **metrics,
    }, indent=2), encoding="utf-8")
    coefs.to_csv(RESULTS_DIR / "coefficients.csv", index=False)

    full_class_counts = y.value_counts().sort_index()
    test_class_counts = y_test.value_counts().sort_index()

    print(f"Trained on {len(df)} synthetic patients "
          f"({len(X_train)} train / {len(X_test)} test, stratified).")
    print("Binary target: 0 = not flagged, 1 = flagged.")
    print(
        f"Class counts in full dataset: 0 = {int(full_class_counts.get(0, 0))}, "
        f"1 = {int(full_class_counts.get(1, 0))}."
    )
    print(
        f"Class counts in test split: 0 = {int(test_class_counts.get(0, 0))}, "
        f"1 = {int(test_class_counts.get(1, 0))}."
    )
    print("Prediction rule: probability >= 0.50 -> predicted class 1, otherwise class 0.")
    print(f"ROC-AUC: {metrics['roc_auc']}  PR-AUC: {metrics['pr_auc']}  "
          f"Brier: {metrics['brier_score']}  positive rate: {metrics['positive_rate_test']}")
    print(f"Saved model + metrics + coefficients to {RESULTS_DIR.relative_to(REPO_ROOT)}")
    print("\nTop coefficients (interpretable benchmark):")
    print(coefs.head(10).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())