"""Model foundation: frame assembly, the synthetic label, and learnability.

Uses a self-contained in-memory fixture (no dependence on the built atlas). The
sklearn-dependent test is guarded so the suite still passes without the `model`
extra installed.
"""

from __future__ import annotations

import numpy as np

from src.model import config as C
from src.model import dataset


def _fixture_records(n_counties: int = 60, seed: int = 0) -> list[dict]:
    """Synthetic counties + patients with feature variance for the label to use."""
    rng = np.random.default_rng(seed)
    recs = []
    for i in range(n_counties):
        patients = [
            {"age": int(rng.integers(28, 80)), "sys": int(rng.normal(128, 14)),
             "dia": int(rng.normal(78, 8)), "a1c": round(float(rng.normal(6.6, 1.4)), 1)}
            for _ in range(int(rng.integers(8, 14)))
        ]
        recs.append({
            "id": f"51{i:03d}", "rural": float(rng.uniform(0, 1)),
            "needIndex": float(rng.uniform(10, 90)), "hpsaScore": int(rng.integers(0, 26)),
            "dom": {"food": float(rng.uniform(10, 90)), "access": float(rng.uniform(10, 90)),
                    "economic": 50.0, "education": 50.0, "environment": 50.0},
            "outcomes": {"diabetes": float(rng.uniform(5, 18)), "bphigh": float(rng.uniform(25, 45)),
                         "obesity": float(rng.uniform(25, 45)), "mhlth": float(rng.uniform(10, 25))},
            "patientsList": patients,
        })
    return recs


def test_synthetic_label_is_deterministic_and_imbalanced():
    recs = _fixture_records()
    X, y1, feats, meta = dataset.patient_frame(recs, seed=1)
    _, y2, _, _ = dataset.patient_frame(recs, seed=1)
    assert (y1.to_numpy() == y2.to_numpy()).all()          # reproducible
    assert 0.05 < float(y1.mean()) < 0.45                  # imbalanced, not degenerate
    assert list(X.columns) == C.PATIENT_FEATURES
    assert not X.isna().any().any()
    assert len(meta) == len(X)


def test_county_frame_shape_and_target():
    recs = _fixture_records()
    X, y, feats = dataset.county_frame(recs)
    assert list(X.columns) == C.COUNTY_FEATURES
    assert not X.isna().any().any()
    assert set(y.unique()) <= {0, 1}
    assert 0.0 < float(y.mean()) < 1.0                     # both classes present


def test_patient_model_beats_base_rate():
    import pytest
    pytest.importorskip("sklearn")
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    X, y, feats, _ = dataset.patient_frame(_fixture_records(n_counties=70, seed=3), seed=3)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=0, stratify=y)
    pipe = make_pipeline(StandardScaler(),
                         LogisticRegression(max_iter=1000, class_weight="balanced"))
    pipe.fit(Xtr, ytr)
    proba = pipe.predict_proba(Xte)[:, 1]
    # The classifier should recover the injected signal: PR-AUC above the base rate.
    assert average_precision_score(yte, proba) > float(yte.mean())


def test_fairness_by_rurality_partitions_all_rows():
    import pytest
    pytest.importorskip("sklearn")
    from src.model import train

    rng = np.random.default_rng(0)
    n = 120
    yte, proba, rural = rng.integers(0, 2, n), rng.random(n), rng.random(n)
    fair = train.fairness_by_rurality(proba, yte, rural)
    assert set(fair["strata"]) == {"more_rural", "less_rural"}
    assert fair["strata"]["more_rural"]["n"] + fair["strata"]["less_rural"]["n"] == n
    for s in fair["strata"].values():
        assert 0.0 <= s["positive_rate"] <= 1.0
