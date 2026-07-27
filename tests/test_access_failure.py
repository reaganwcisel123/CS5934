"""Tests for the national Rural Care Access Failure model path."""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
import pytest

from src.build_dataset import (
    _access_failure_model_metadata,
    _attach_access_failure_predictions,
)
from src.catalog import Catalog
from src.model import config as C
from src.model import dataset


def _source_frame(rows: int = 40) -> pd.DataFrame:
    values = []
    for index in range(rows):
        state = "51" if index < 6 else "01"
        values.append(
            {
                "county_fips": f"{state}{index + 1:03d}",
                "preventable_hospital_stays": 1000 + (index * 50),
                "uninsured_percent": 5 + (index % 20),
                "primary_care_physician_burden": 500 + (index * 10),
                "mental_health_provider_burden": 300 + (index * 8),
                "other_primary_care_provider_burden": 400 + (index * 7),
                "broadband_access_percent": 95 - (index % 30),
                "source_year": 2026,
            }
        )
    frame = pd.DataFrame(values)
    frame.loc[0, "uninsured_percent"] = np.nan
    return frame


def test_access_failure_frame_uses_national_threshold_and_has_no_leakage():
    frame = _source_frame()
    X, y, features, metadata = dataset.access_failure_frame(frame)

    expected = frame["preventable_hospital_stays"].quantile(C.ACCESS_FAILURE_QUANTILE)
    assert metadata.attrs["target_threshold"] == expected
    assert list(X.columns) == features
    assert C.ACCESS_FAILURE_TARGET not in features
    assert "high_access_failure" not in features
    assert X.loc[1, "broadband_gap"] == 6
    assert y.mean() == 0.25


def test_prediction_attachment_uses_fips_and_leaves_missing_predictions_absent(tmp_path):
    prediction_path = tmp_path / "predictions.json"
    prediction_path.write_text(
        json.dumps(
            {
                "predictions": [
                    {
                        "county_fips": "51001",
                        "probability": 0.78,
                        "riskTier": "High",
                        "predictedHighRisk": True,
                        "observedPreventableStays": 4200.0,
                        "topDrivers": ["Limited primary-care capacity"],
                        "explanationMethod": "logistic-coefficients",
                        "dataYear": 2026,
                        "modelVersion": "access-failure-v1",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    records = [{"id": "51001"}, {"id": "51003"}]

    assert _attach_access_failure_predictions(records, prediction_path) == 1
    assert records[0]["accessFailureRisk"]["probability"] == 0.78
    assert "accessFailureRisk" not in records[1]


def test_prediction_attachment_skips_invalid_scores(tmp_path):
    prediction_path = tmp_path / "predictions.json"
    prediction_path.write_text(
        json.dumps(
            {
                "predictions": [
                    {"county_fips": "51001", "probability": float("nan"), "riskTier": "High"},
                    {"county_fips": "51003", "probability": 0.8, "riskTier": "Unknown"},
                ]
            }
        ),
        encoding="utf-8",
    )
    records = [{"id": "51001"}, {"id": "51003"}]

    assert _attach_access_failure_predictions(records, prediction_path) == 0
    assert all("accessFailureRisk" not in record for record in records)


def test_access_failure_model_metadata_uses_generated_artifacts_and_catalog(tmp_path):
    metrics_path = tmp_path / "metrics.json"
    model_card_path = tmp_path / "model_card.json"
    metrics_path.write_text(
        json.dumps(
            {
                "best_model": "logreg",
                "models": {"logreg": {"pr_auc": 0.4, "roc_auc": 0.6, "brier": 0.2}},
                "target_definition": "Example target",
                "features": ["uninsured_percent"],
                "positive_rate": 0.25,
                "split_strategy": "stratified",
                "n_total": 40,
                "n_train": 30,
                "n_test": 10,
                "virginia_prediction_count": 6,
                "selection_metric": "mean cross-validation PR-AUC",
                "display_tier_thresholds": {"high": 0.67, "medium": 0.33},
            }
        ),
        encoding="utf-8",
    )
    model_card_path.write_text(
        json.dumps(
            {
                "modelVersion": "access-failure-v1",
                "outcome": "High preventable hospital stays",
                "sourceYear": 2026,
                "targetThreshold": 3000.0,
            }
        ),
        encoding="utf-8",
    )

    metadata = _access_failure_model_metadata(
        Catalog.load(), metrics_path, model_card_path
    )

    assert metadata is not None
    assert metadata["selectedModel"] == "logreg"
    assert metadata["performance"]["prAuc"] == 0.4
    assert metadata["sourceUrl"].startswith("https://www.countyhealthrankings.org/")


def test_access_failure_cli_target_and_artifact(tmp_path, monkeypatch):
    pytest.importorskip("sklearn")
    pytest.importorskip("joblib")

    from src.model import train

    frame = _source_frame()
    frame_builder = dataset.access_failure_frame
    monkeypatch.setattr(
        dataset,
        "access_failure_frame",
        lambda: frame_builder(frame),
    )
    monkeypatch.setattr(C, "CV_SPLITS", 3)
    monkeypatch.setattr(C, "CV_REPEATS", 1)
    monkeypatch.setattr(train, "ACCESS_FAILURE_DIR", tmp_path / "access_failure")

    metrics = train.train_one("access-failure")

    assert metrics["target"] == "access-failure"
    assert metrics["target_threshold"] == frame["preventable_hospital_stays"].quantile(0.75)
    assert {"logreg", "gboost"} == set(metrics["models"])
    assert (tmp_path / "access_failure" / "model.joblib").exists()
    assert (tmp_path / "access_failure" / "metrics.json").exists()
    predictions = json.loads(
        (tmp_path / "access_failure" / "predictions.json").read_text(encoding="utf-8")
    )["predictions"]
    assert predictions and all(row["county_fips"].startswith("51") for row in predictions)

    received = []
    monkeypatch.setattr(train, "train_one", lambda target: received.append(target))
    monkeypatch.setattr(sys, "argv", ["train.py", "--target", "access-failure"])
    assert train.main() == 0
    assert received == ["access-failure"]
