"""Score patients and counties using the trained model artifacts.

Run:

    python -m src.model.score

New patient model artifacts contain fixed risk-tier thresholds learned from the
training population. Older model-only joblib files are still supported and use
batch-relative quantiles as a fallback.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[2]),
)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.catalog import REPO_ROOT  # noqa: E402
from src.model import config as C  # noqa: E402

ATLAS_PATH = (
    REPO_ROOT
    / "dashboard"
    / "data"
    / "clinic_atlas.json"
)

MODEL_PATH = (
    REPO_ROOT
    / "models"
    / "patient_model.joblib"
)

COUNTY_MODEL_PATH = (
    REPO_ROOT
    / "models"
    / "county_model.joblib"
)


def load_patient_model():
    """Return the trained patient model artifact, or None if unavailable."""
    if not MODEL_PATH.exists():
        return None

    import joblib

    return joblib.load(MODEL_PATH)


def load_county_model():
    """Return the trained county model artifact, or None if unavailable."""
    if not COUNTY_MODEL_PATH.exists():
        return None

    import joblib

    return joblib.load(
        COUNTY_MODEL_PATH
    )


def _unpack(
    model_or_artifact,
    default_features,
):
    """Support new artifact dictionaries and older model-only joblib files."""
    if (
        isinstance(
            model_or_artifact,
            dict,
        )
        and "model"
        in model_or_artifact
    ):
        return (
            model_or_artifact["model"],
            model_or_artifact.get(
                "features",
                default_features,
            ),
            model_or_artifact.get(
                "tier_thresholds"
            ),
        )

    return (
        model_or_artifact,
        default_features,
        None,
    )


def score_counties(
    records: list[dict],
    model_or_artifact,
) -> int:
    """Attach modelRisk and modelRiskDrivers to each usable county."""
    model, features, _ = _unpack(
        model_or_artifact,
        C.COUNTY_FEATURES,
    )

    rows = []
    references = []

    for record in records:
        domains = record.get(
            "dom",
            {},
        )

        feature_values = {
            "food": domains.get("food"),
            "access": domains.get("access"),
            "economic": domains.get(
                "economic"
            ),
            "education": domains.get(
                "education"
            ),
            "environment": domains.get(
                "environment"
            ),
            "hpsaScore": record.get(
                "hpsaScore"
            ),
            "rural": record.get("rural"),
            "needIndex": record.get(
                "needIndex"
            ),
        }

        if any(
            feature_values.get(feature)
            is None
            for feature in features
        ):
            continue

        rows.append(
            [
                feature_values[feature]
                for feature in features
            ]
        )

        references.append(record)

    if not rows:
        return 0

    X = pd.DataFrame(
        rows,
        columns=features,
    )

    X_array = X.to_numpy(
        dtype=float
    )

    probabilities = model.predict_proba(
        X
    )[:, 1]

    driver_function = _driver_fn(
        model
    )

    for index, record in enumerate(
        references
    ):
        record["modelRisk"] = round(
            float(
                probabilities[index]
            ),
            3,
        )

        record["modelRiskDrivers"] = (
            _top_drivers(
                driver_function(
                    X_array[index]
                ),
                features,
                C.COUNTY_DRIVER_LABELS,
            )
            if driver_function
            else []
        )

    return len(references)


def _driver_fn(model):
    """Return a contribution function for a logistic-regression pipeline."""
    steps = getattr(
        model,
        "named_steps",
        {},
    )

    if (
        "logisticregression"
        not in steps
        or "standardscaler"
        not in steps
    ):
        return None

    coefficients = steps[
        "logisticregression"
    ].coef_[0]

    means = steps[
        "standardscaler"
    ].mean_

    scales = steps[
        "standardscaler"
    ].scale_

    return lambda row: (
        coefficients
        * (
            (
                np.asarray(
                    row,
                    dtype=float,
                )
                - means
            )
            / scales
        )
    )


def _top_drivers(
    contributions: np.ndarray,
    features: list[str],
    labels: dict,
    k: int = 2,
) -> list[str]:
    """Return the top distinct positive, human-readable risk drivers."""
    output: list[str] = []

    for index in np.argsort(
        contributions
    )[::-1]:
        if contributions[index] <= 0:
            break

        label = labels.get(
            features[index]
        )

        if (
            label is None
            or label in output
        ):
            continue

        output.append(label)

        if len(output) >= k:
            break

    return output


def score_records(
    records: list[dict],
    model_or_artifact,
) -> int:
    """Attach risk, riskTier, and riskDrivers to each usable patient."""
    (
        model,
        features,
        stored_thresholds,
    ) = _unpack(
        model_or_artifact,
        C.PATIENT_FEATURES,
    )

    rows = []
    references = []

    for record in records:
        domains = record.get(
            "dom",
            {},
        )

        county_context = {
            "ctx_food": domains.get(
                "food"
            ),
            "ctx_access": domains.get(
                "access"
            ),
            "rural": record.get("rural"),
            "needIndex": record.get(
                "needIndex"
            ),
        }

        for patient in record.get(
            "patientsList",
            [],
        ):
            feature_values = {
                "age": patient.get("age"),
                "sys": patient.get("sys"),
                "dia": patient.get("dia"),
                "a1c": patient.get("a1c"),
                **county_context,
            }

            if any(
                feature_values.get(feature)
                is None
                for feature in features
            ):
                continue

            rows.append(
                [
                    feature_values[feature]
                    for feature in features
                ]
            )

            references.append(patient)

    if not rows:
        return 0

    X = pd.DataFrame(
        rows,
        columns=features,
    )

    X_array = X.to_numpy(
        dtype=float
    )

    probabilities = model.predict_proba(
        X
    )[:, 1]

    if stored_thresholds:
        high_threshold = float(
            stored_thresholds["high"]
        )
        medium_threshold = float(
            stored_thresholds["medium"]
        )
    else:
        # Backward compatibility for older model-only artifacts.
        high_threshold = float(
            np.quantile(
                probabilities,
                C.TIER_QUANTILES["high"],
            )
        )

        medium_threshold = float(
            np.quantile(
                probabilities,
                C.TIER_QUANTILES["medium"],
            )
        )

    if high_threshold < medium_threshold:
        raise ValueError(
            "High risk-tier threshold "
            "cannot be below Medium."
        )

    driver_function = _driver_fn(
        model
    )

    for index, patient in enumerate(
        references
    ):
        probability = float(
            probabilities[index]
        )

        patient["risk"] = round(
            probability,
            3,
        )

        if probability >= high_threshold:
            patient["riskTier"] = "High"
        elif probability >= medium_threshold:
            patient["riskTier"] = "Medium"
        else:
            patient["riskTier"] = "Low"

        patient["riskDrivers"] = (
            _top_drivers(
                driver_function(
                    X_array[index]
                ),
                features,
                C.DRIVER_LABELS,
            )
            if driver_function
            else []
        )

    return len(references)


def main() -> int:
    patient_model = load_patient_model()
    county_model = load_county_model()

    if (
        patient_model is None
        and county_model is None
    ):
        print(
            "No trained models found -- run "
            "`python -m src.model.train` first."
        )
        return 1

    data = json.loads(
        ATLAS_PATH.read_text(
            encoding="utf-8"
        )
    )

    patient_count = (
        score_records(
            data["records"],
            patient_model,
        )
        if patient_model
        else 0
    )

    county_count = (
        score_counties(
            data["records"],
            county_model,
        )
        if county_model
        else 0
    )

    ATLAS_PATH.write_text(
        json.dumps(
            data,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    print(
        f"Scored {patient_count} patients + "
        f"{county_count} counties into "
        f"{ATLAS_PATH.relative_to(REPO_ROOT)}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())