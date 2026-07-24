"""Model foundation tests.

The fixture is self-contained and does not depend on a locally built atlas.
Sklearn-dependent tests are guarded so the broader test suite can still run
without the optional `model` dependency installed.
"""

from __future__ import annotations

import numpy as np

from src.model import config as C
from src.model import dataset


def _fixture_records(
    n_counties: int = 60,
    seed: int = 0,
) -> list[dict]:
    """Create counties and patients with enough variance for testing."""
    rng = np.random.default_rng(seed)
    records = []

    for index in range(n_counties):
        patients = [
            {
                "age": int(
                    rng.integers(28, 80)
                ),
                "sys": int(
                    rng.normal(128, 14)
                ),
                "dia": int(
                    rng.normal(78, 8)
                ),
                "a1c": round(
                    float(
                        rng.normal(6.6, 1.4)
                    ),
                    1,
                ),
            }
            for _ in range(
                int(
                    rng.integers(8, 14)
                )
            )
        ]

        records.append(
            {
                "id": f"51{index:03d}",
                "rural": float(
                    rng.uniform(0, 1)
                ),
                "needIndex": float(
                    rng.uniform(10, 90)
                ),
                "hpsaScore": int(
                    rng.integers(0, 26)
                ),
                "dom": {
                    "food": float(
                        rng.uniform(10, 90)
                    ),
                    "access": float(
                        rng.uniform(10, 90)
                    ),
                    "economic": 50.0,
                    "education": 50.0,
                    "environment": 50.0,
                },
                "outcomes": {
                    "diabetes": float(
                        rng.uniform(5, 18)
                    ),
                    "bphigh": float(
                        rng.uniform(25, 45)
                    ),
                    "obesity": float(
                        rng.uniform(25, 45)
                    ),
                    "mhlth": float(
                        rng.uniform(10, 25)
                    ),
                },
                "patientsList": patients,
            }
        )

    return records


def test_synthetic_label_is_deterministic_and_imbalanced():
    records = _fixture_records()

    X, y_first, _, metadata = dataset.patient_frame(
        records,
        seed=1,
    )

    _, y_second, _, _ = dataset.patient_frame(
        records,
        seed=1,
    )

    assert (
        y_first.to_numpy()
        == y_second.to_numpy()
    ).all()

    assert (
        0.05
        < float(y_first.mean())
        < 0.45
    )

    assert list(X.columns) == C.PATIENT_FEATURES
    assert not X.isna().any().any()
    assert len(metadata) == len(X)


def test_county_frame_shape_and_target():
    X, y, _ = dataset.county_frame(
        _fixture_records()
    )

    assert list(X.columns) == C.COUNTY_FEATURES
    assert not X.isna().any().any()
    assert set(y.unique()) <= {0, 1}
    assert 0.0 < float(y.mean()) < 1.0


def test_patient_metadata_stays_aligned_after_incomplete_row_is_removed():
    records = _fixture_records(
        n_counties=2,
        seed=9,
    )

    records[0][
        "patientsList"
    ][0]["a1c"] = None

    X, _, _, metadata = dataset.patient_frame(
        records,
        seed=9,
    )

    expected_first_county_rows = (
        len(
            records[0]["patientsList"]
        )
        - 1
    )

    assert len(X) == len(metadata)

    assert (
        metadata.iloc[
            :expected_first_county_rows
        ]["county_fips"]
        == records[0]["id"]
    ).all()

    assert (
        metadata.iloc[
            expected_first_county_rows:
        ]["county_fips"]
        == records[1]["id"]
    ).all()


def test_patient_model_beats_base_rate():
    import pytest

    pytest.importorskip("sklearn")

    from sklearn.linear_model import (
        LogisticRegression,
    )
    from sklearn.metrics import (
        average_precision_score,
    )
    from sklearn.model_selection import (
        train_test_split,
    )
    from sklearn.pipeline import (
        make_pipeline,
    )
    from sklearn.preprocessing import (
        StandardScaler,
    )

    X, y, _, _ = dataset.patient_frame(
        _fixture_records(
            n_counties=70,
            seed=3,
        ),
        seed=3,
    )

    (
        X_train,
        X_test,
        y_train,
        y_test,
    ) = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=0,
        stratify=y,
    )

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
        ),
    )

    model.fit(
        X_train,
        y_train,
    )

    probabilities = model.predict_proba(
        X_test
    )[:, 1]

    assert (
        average_precision_score(
            y_test,
            probabilities,
        )
        > float(y_test.mean())
    )


def test_patient_holdout_has_no_county_overlap():
    import pytest

    pytest.importorskip("sklearn")

    from src.model import train

    X, y, _, metadata = dataset.patient_frame(
        _fixture_records(
            n_counties=70,
            seed=4,
        ),
        seed=4,
    )

    groups = metadata["county_fips"]

    (
        train_indices,
        test_indices,
    ) = train._holdout_indices(
        "patient",
        X,
        y,
        groups,
    )

    training_counties = set(
        groups.iloc[train_indices]
    )

    testing_counties = set(
        groups.iloc[test_indices]
    )

    assert training_counties.isdisjoint(
        testing_counties
    )

    assert set(
        y.iloc[train_indices].unique()
    ) == {0, 1}

    assert set(
        y.iloc[test_indices].unique()
    ) == {0, 1}


def test_repeated_group_cross_validation_reports_variability(
    monkeypatch,
):
    import pytest

    pytest.importorskip("sklearn")

    from sklearn.linear_model import (
        LogisticRegression,
    )
    from sklearn.pipeline import (
        make_pipeline,
    )
    from sklearn.preprocessing import (
        StandardScaler,
    )

    from src.model import train

    monkeypatch.setattr(
        C,
        "CV_SPLITS",
        3,
    )

    monkeypatch.setattr(
        C,
        "CV_REPEATS",
        2,
    )

    X, y, _, metadata = dataset.patient_frame(
        _fixture_records(
            n_counties=45,
            seed=12,
        ),
        seed=12,
    )

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
        ),
    )

    summary = train._cross_validate(
        "patient",
        "logreg",
        model,
        X,
        y,
        metadata["county_fips"],
    )

    assert summary["folds"] == 6

    for metric in (
        "pr_auc",
        "roc_auc",
        "brier",
    ):
        assert (
            0.0
            <= summary[
                f"{metric}_mean"
            ]
            <= 1.0
        )

        assert (
            summary[
                f"{metric}_std"
            ]
            >= 0.0
        )


def test_fairness_by_rurality_partitions_all_rows():
    import pytest

    pytest.importorskip("sklearn")

    from src.model import train

    rng = np.random.default_rng(0)
    row_count = 120

    y_test = rng.integers(
        0,
        2,
        row_count,
    )

    probabilities = rng.random(
        row_count
    )

    rurality = rng.random(
        row_count
    )

    fairness = train.fairness_by_rurality(
        probabilities,
        y_test,
        rurality,
    )

    assert set(
        fairness["strata"]
    ) == {
        "more_rural",
        "less_rural",
    }

    assert (
        fairness["strata"][
            "more_rural"
        ]["n"]
        + fairness["strata"][
            "less_rural"
        ]["n"]
        == row_count
    )

    for stratum in fairness[
        "strata"
    ].values():
        assert (
            0.0
            <= stratum["positive_rate"]
            <= 1.0
        )


def test_score_records_adds_tier_and_drivers():
    import pytest

    pytest.importorskip("sklearn")

    from sklearn.linear_model import (
        LogisticRegression,
    )
    from sklearn.pipeline import (
        make_pipeline,
    )
    from sklearn.preprocessing import (
        StandardScaler,
    )

    from src.model import score

    records = _fixture_records(
        n_counties=40,
        seed=5,
    )

    X, y, _, _ = dataset.patient_frame(
        records,
        seed=5,
    )

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
        ),
    ).fit(X, y)

    count = score.score_records(
        records,
        model,
    )

    scored_patients = [
        patient
        for county in records
        for patient in county[
            "patientsList"
        ]
        if "risk" in patient
    ]

    assert (
        count
        == len(scored_patients)
        > 0
    )

    assert {
        patient["riskTier"]
        for patient in scored_patients
    } <= {
        "High",
        "Medium",
        "Low",
    }

    assert any(
        patient["riskTier"] == "High"
        for patient in scored_patients
    )

    for patient in scored_patients:
        assert (
            0.0
            <= patient["risk"]
            <= 1.0
        )

        assert isinstance(
            patient["riskDrivers"],
            list,
        )


def test_score_records_uses_stored_training_thresholds():
    import pytest

    pytest.importorskip("sklearn")

    from src.model import score

    class AgeProbabilityModel:
        def predict_proba(self, X):
            probabilities = (
                X["age"].to_numpy(
                    dtype=float
                )
                / 100.0
            )

            return np.column_stack(
                [
                    1.0 - probabilities,
                    probabilities,
                ]
            )

    records = [
        {
            "id": "51001",
            "rural": 0.4,
            "needIndex": 50.0,
            "dom": {
                "food": 40.0,
                "access": 60.0,
            },
            "patientsList": [
                {
                    "age": 30,
                    "sys": 120,
                    "dia": 75,
                    "a1c": 5.5,
                },
                {
                    "age": 50,
                    "sys": 125,
                    "dia": 78,
                    "a1c": 6.2,
                },
                {
                    "age": 80,
                    "sys": 135,
                    "dia": 82,
                    "a1c": 7.8,
                },
            ],
        }
    ]

    model_artifact = {
        "model": AgeProbabilityModel(),
        "features": C.PATIENT_FEATURES,
        "tier_thresholds": {
            "high": 0.70,
            "medium": 0.40,
        },
    }

    score.score_records(
        records,
        model_artifact,
    )

    tiers = [
        patient["riskTier"]
        for patient in records[0][
            "patientsList"
        ]
    ]

    assert tiers == [
        "Low",
        "Medium",
        "High",
    ]