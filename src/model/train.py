"""Train and evaluate county and patient risk classifiers.

Run:

    python -m src.model.train --target both
    python -m src.model.train --target patient

The workflow compares logistic regression and gradient boosting, reports
holdout and repeated cross-validation results, evaluates rurality fairness,
keeps patients from the same county together, and stores fixed patient
risk-tier thresholds with the final model.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow both:
# python -m src.model.train
# python src/model/train.py
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[2]),
)

import joblib  # noqa: E402
import numpy as np  # noqa: E402

from sklearn.base import clone  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.model_selection import (  # noqa: E402
    GroupShuffleSplit,
    RepeatedStratifiedKFold,
    StratifiedGroupKFold,
    train_test_split,
)
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.utils.class_weight import compute_sample_weight  # noqa: E402

from src.catalog import REPO_ROOT  # noqa: E402
from src.model import config as C  # noqa: E402
from src.model import dataset  # noqa: E402

MODELS_DIR = REPO_ROOT / "models"


def _build(target: str):
    """Build the feature frame, target, features, and optional county groups."""
    if target == "county":
        X, y, features = dataset.county_frame()
        return X, y, features, None

    if target == "patient":
        X, y, features, metadata = dataset.patient_frame()
        return X, y, features, metadata["county_fips"]

    raise ValueError(f"Unknown target: {target}")


def _make_models() -> dict:
    """Return the baseline and advanced candidate models."""
    return {
        "logreg": make_pipeline(
            StandardScaler(),
            LogisticRegression(
                max_iter=1000,
                class_weight="balanced",
                random_state=C.RANDOM_STATE,
            ),
        ),
        "gboost": HistGradientBoostingClassifier(
            random_state=C.RANDOM_STATE,
        ),
    }


def _fit(name: str, model, X_train, y_train):
    """Fit a model while handling class imbalance."""
    if name == "gboost":
        sample_weights = compute_sample_weight(
            "balanced",
            y_train,
        )
        model.fit(
            X_train,
            y_train,
            sample_weight=sample_weights,
        )
    else:
        model.fit(X_train, y_train)

    return model


def _raw_score(y_true, probabilities) -> dict:
    """Return unrounded metrics for aggregation."""
    return {
        "pr_auc": float(
            average_precision_score(
                y_true,
                probabilities,
            )
        ),
        "roc_auc": float(
            roc_auc_score(
                y_true,
                probabilities,
            )
        ),
        "brier": float(
            brier_score_loss(
                y_true,
                probabilities,
            )
        ),
    }


def _score(y_true, probabilities) -> dict:
    """Return rounded metrics for JSON output and display."""
    return {
        metric: round(value, 3)
        for metric, value in _raw_score(
            y_true,
            probabilities,
        ).items()
    }


def _holdout_indices(
    target,
    X,
    y,
    groups=None,
):
    """Create a holdout split.

    County modeling uses a standard stratified split. Patient modeling uses
    county groups so patients sharing county-level features never appear in
    both training and testing.
    """
    if target == "patient":
        splitter = GroupShuffleSplit(
            n_splits=25,
            test_size=C.TEST_SIZE,
            random_state=C.RANDOM_STATE,
        )

        for train_indices, test_indices in splitter.split(
            X,
            y,
            groups=groups,
        ):
            train_has_both_classes = (
                y.iloc[train_indices].nunique() == 2
            )
            test_has_both_classes = (
                y.iloc[test_indices].nunique() == 2
            )

            if (
                train_has_both_classes
                and test_has_both_classes
            ):
                return train_indices, test_indices

        raise ValueError(
            "Could not create a county-grouped patient split "
            "containing both target classes."
        )

    all_indices = np.arange(len(X))

    train_indices, test_indices = train_test_split(
        all_indices,
        test_size=C.TEST_SIZE,
        random_state=C.RANDOM_STATE,
        stratify=y,
    )

    return train_indices, test_indices


def _cv_splits(
    target,
    X,
    y,
    groups=None,
):
    """Yield repeated cross-validation splits."""
    if target == "county":
        cross_validator = RepeatedStratifiedKFold(
            n_splits=C.CV_SPLITS,
            n_repeats=C.CV_REPEATS,
            random_state=C.RANDOM_STATE,
        )

        yield from cross_validator.split(X, y)
        return

    # sklearn does not provide a RepeatedStratifiedGroupKFold class, so create
    # one shuffled StratifiedGroupKFold per repeat with a different fixed seed.
    for repeat in range(C.CV_REPEATS):
        cross_validator = StratifiedGroupKFold(
            n_splits=C.CV_SPLITS,
            shuffle=True,
            random_state=C.RANDOM_STATE + repeat,
        )

        yield from cross_validator.split(
            X,
            y,
            groups=groups,
        )


def _cross_validate(
    target,
    name,
    model,
    X,
    y,
    groups=None,
) -> dict:
    """Evaluate a candidate across repeated folds."""
    fold_scores = []

    for train_indices, test_indices in _cv_splits(
        target,
        X,
        y,
        groups,
    ):
        y_train = y.iloc[train_indices]
        y_test = y.iloc[test_indices]

        if (
            y_train.nunique() < 2
            or y_test.nunique() < 2
        ):
            continue

        fitted_model = _fit(
            name,
            clone(model),
            X.iloc[train_indices],
            y_train,
        )

        probabilities = fitted_model.predict_proba(
            X.iloc[test_indices]
        )[:, 1]

        fold_scores.append(
            _raw_score(
                y_test,
                probabilities,
            )
        )

    if not fold_scores:
        raise ValueError(
            f"No valid cross-validation folds for {target}/{name}."
        )

    summary = {
        "folds": len(fold_scores),
    }

    for metric in (
        "pr_auc",
        "roc_auc",
        "brier",
    ):
        values = np.array(
            [
                score[metric]
                for score in fold_scores
            ],
            dtype=float,
        )

        summary[f"{metric}_mean"] = round(
            float(values.mean()),
            3,
        )
        summary[f"{metric}_std"] = round(
            float(values.std()),
            3,
        )

    return summary


def fairness_by_rurality(
    probabilities,
    y_test,
    rurality,
) -> dict:
    """Report PR-AUC and prevalence above and below median rurality."""
    rurality = np.asarray(
        rurality,
        dtype=float,
    )
    y_test = np.asarray(y_test)
    probabilities = np.asarray(probabilities)

    threshold = float(
        np.median(rurality)
    )

    output = {
        "threshold": round(threshold, 3),
        "strata": {},
    }

    strata = (
        (
            "more_rural",
            rurality >= threshold,
        ),
        (
            "less_rural",
            rurality < threshold,
        ),
    )

    for label, mask in strata:
        group_y = y_test[mask]
        group_probabilities = probabilities[mask]

        has_both_classes = (
            len(set(group_y.tolist())) == 2
        )

        output["strata"][label] = {
            "n": int(mask.sum()),
            "positive_rate": round(
                float(group_y.mean())
                if len(group_y)
                else 0.0,
                3,
            ),
            "pr_auc": (
                round(
                    float(
                        average_precision_score(
                            group_y,
                            group_probabilities,
                        )
                    ),
                    3,
                )
                if has_both_classes
                else None
            ),
        }

    return output


def _rurality_mitigation(
    model,
    name,
    X_train,
    y_train,
    X_test,
    y_test,
) -> dict:
    """Refit with equal rural-stratum weight and remeasure fairness."""
    threshold = float(
        np.median(
            X_train["rural"].to_numpy()
        )
    )

    rurality_group = (
        X_train["rural"].to_numpy()
        >= threshold
    ).astype(int)

    sample_weights = compute_sample_weight(
        "balanced",
        rurality_group,
    )

    mitigated_model = clone(model)

    if name == "logreg":
        mitigated_model.fit(
            X_train,
            y_train,
            logisticregression__sample_weight=sample_weights,
        )
    else:
        mitigated_model.fit(
            X_train,
            y_train,
            sample_weight=sample_weights,
        )

    probabilities = mitigated_model.predict_proba(
        X_test
    )[:, 1]

    return fairness_by_rurality(
        probabilities,
        y_test,
        X_test["rural"].to_numpy(),
    )


def _select_best(
    target: str,
    cross_validation_results: dict,
) -> str:
    """Select by mean CV PR-AUC while favoring interpretability near a tie."""
    best_model = max(
        cross_validation_results,
        key=lambda model_name: (
            cross_validation_results[
                model_name
            ]["pr_auc_mean"]
        ),
    )

    interpretability_margin = (
        0.08
        if target == "county"
        else 0.02
    )

    logistic_score = (
        cross_validation_results[
            "logreg"
        ]["pr_auc_mean"]
    )

    best_score = (
        cross_validation_results[
            best_model
        ]["pr_auc_mean"]
    )

    if (
        logistic_score
        >= best_score
        - interpretability_margin
    ):
        return "logreg"

    return best_model


def train_one(target: str) -> dict:
    """Train candidates, evaluate them, and persist the selected model."""
    X, y, features, groups = _build(target)

    train_indices, test_indices = _holdout_indices(
        target,
        X,
        y,
        groups,
    )

    X_train = X.iloc[train_indices]
    X_test = X.iloc[test_indices]
    y_train = y.iloc[train_indices]
    y_test = y.iloc[test_indices]

    candidates = _make_models()

    fitted_models = {}
    holdout_results = {}
    holdout_probabilities = {}
    cross_validation_results = {}

    for name, candidate in candidates.items():
        cross_validation_results[name] = _cross_validate(
            target,
            name,
            candidate,
            X,
            y,
            groups,
        )

        fitted_model = _fit(
            name,
            clone(candidate),
            X_train,
            y_train,
        )

        probabilities = fitted_model.predict_proba(
            X_test
        )[:, 1]

        fitted_models[name] = fitted_model
        holdout_probabilities[name] = probabilities
        holdout_results[name] = _score(
            y_test,
            probabilities,
        )

    best_model_name = _select_best(
        target,
        cross_validation_results,
    )

    fairness = fairness_by_rurality(
        holdout_probabilities[best_model_name],
        y_test,
        X_test["rural"].to_numpy(),
    )

    mitigated_fairness = _rurality_mitigation(
        fitted_models[best_model_name],
        best_model_name,
        X_train,
        y_train,
        X_test,
        y_test,
    )

    metrics = {
        "target": target,
        "n_total": int(len(X)),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "features": features,
        "positive_rate": round(
            float(y.mean()),
            3,
        ),
        "split_strategy": (
            "county-grouped"
            if target == "patient"
            else "stratified"
        ),
        "models": holdout_results,
        "cross_validation": cross_validation_results,
        "best_model": best_model_name,
        "selection_metric": (
            "mean cross-validation PR-AUC"
        ),
        "fairness_by_rurality": fairness,
        "fairness_after_mitigation": (
            mitigated_fairness
        ),
    }

    if (
        target == "patient"
        and groups is not None
    ):
        training_counties = set(
            groups.iloc[train_indices]
        )
        testing_counties = set(
            groups.iloc[test_indices]
        )

        metrics["county_group_split"] = {
            "train_counties": len(
                training_counties
            ),
            "test_counties": len(
                testing_counties
            ),
            "overlap_count": len(
                training_counties
                & testing_counties
            ),
        }

    # After model selection and evaluation, refit the chosen production model
    # using all available rows.
    final_model = _fit(
        best_model_name,
        clone(candidates[best_model_name]),
        X,
        y,
    )

    model_artifact = {
        "model": final_model,
        "features": features,
        "target": target,
        "model_name": best_model_name,
    }

    if target == "patient":
        training_probabilities = (
            final_model.predict_proba(X)[:, 1]
        )

        model_artifact["tier_thresholds"] = {
            "high": float(
                np.quantile(
                    training_probabilities,
                    C.TIER_QUANTILES["high"],
                )
            ),
            "medium": float(
                np.quantile(
                    training_probabilities,
                    C.TIER_QUANTILES["medium"],
                )
            ),
        }

        metrics["tier_thresholds"] = (
            model_artifact[
                "tier_thresholds"
            ]
        )

    MODELS_DIR.mkdir(exist_ok=True)

    joblib.dump(
        model_artifact,
        MODELS_DIR
        / f"{target}_model.joblib",
    )

    (
        MODELS_DIR
        / f"{target}_metrics.json"
    ).write_text(
        json.dumps(
            metrics,
            indent=2,
        ),
        encoding="utf-8",
    )

    _report(metrics)
    return metrics


def _report(metrics: dict) -> None:
    """Print a concise training report."""
    print(
        f"\n=== {metrics['target']} model ==="
    )

    print(
        f"  rows={metrics['n_total']}  "
        f"train={metrics['n_train']}  "
        f"test={metrics['n_test']}  "
        f"features={len(metrics['features'])}  "
        f"base_rate={metrics['positive_rate']:.3f}"
    )

    if "county_group_split" in metrics:
        split = metrics[
            "county_group_split"
        ]

        print(
            "  county split: "
            f"train={split['train_counties']} "
            f"test={split['test_counties']} "
            f"overlap={split['overlap_count']}"
        )

    print(
        f"  {'model':8}"
        f"{'holdout PR':>12}"
        f"{'CV PR mean':>12}"
        f"{'CV PR std':>11}"
        f"{'Brier':>8}"
    )

    for name, result in metrics[
        "models"
    ].items():
        cross_validation = metrics[
            "cross_validation"
        ][name]

        selected = (
            "  <- best"
            if name
            == metrics["best_model"]
            else ""
        )

        print(
            f"  {name:8}"
            f"{result['pr_auc']:>12.3f}"
            f"{cross_validation['pr_auc_mean']:>12.3f}"
            f"{cross_validation['pr_auc_std']:>11.3f}"
            f"{result['brier']:>8.3f}"
            f"{selected}"
        )

    def print_fairness(
        title: str,
        fairness_result: dict,
    ) -> None:
        print(
            f"  {title} "
            f"(split at rural="
            f"{fairness_result['threshold']}):"
        )

        for label, result in fairness_result[
            "strata"
        ].items():
            pr_auc = (
                f"{result['pr_auc']:.3f}"
                if result["pr_auc"]
                is not None
                else "n/a"
            )

            print(
                f"    {label:11} "
                f"n={result['n']:>3}  "
                f"pos_rate="
                f"{result['positive_rate']:.3f}  "
                f"PR-AUC={pr_auc}"
            )

    print_fairness(
        "rurality fairness (best model)",
        metrics["fairness_by_rurality"],
    )

    print_fairness(
        "after rurality-balanced retrain",
        metrics[
            "fairness_after_mitigation"
        ],
    )

    if "tier_thresholds" in metrics:
        thresholds = metrics[
            "tier_thresholds"
        ]

        print(
            "  fixed tiers: "
            f"High >= "
            f"{thresholds['high']:.3f}; "
            f"Medium >= "
            f"{thresholds['medium']:.3f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--target",
        choices=[
            "county",
            "patient",
            "both",
        ],
        default="both",
    )

    args = parser.parse_args()

    targets = (
        ["county", "patient"]
        if args.target == "both"
        else [args.target]
    )

    for target in targets:
        train_one(target)

    print(
        "\nSaved best models and metrics to "
        f"{MODELS_DIR.relative_to(REPO_ROOT)}/"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())