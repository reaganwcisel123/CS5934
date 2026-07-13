"""Writer helpers that shape scored patients + county risk for Postgres.

Pure (no DB): the live round-trip is exercised end-to-end via the API.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("sqlalchemy")

from src.db import writer  # noqa: E402


def test_patient_rows_flattens_and_promotes_fields():
    rec = {"id": "51001", "patientsList": [
        {"name": "A", "age": 60, "risk": 0.8, "riskTier": "High", "riskDrivers": ["Elevated A1c"], "a1c": 7.0, "sys": 140},
        {"name": "B", "age": 40, "risk": 0.1, "riskTier": "Low", "riskDrivers": [], "a1c": 5.5},
    ]}
    rows = writer._patient_rows(rec)
    assert len(rows) == 2
    assert rows[0]["fips"] == "51001" and rows[0]["name"] == "A" and rows[0]["tier"] == "High"
    assert json.loads(rows[0]["drivers"]) == ["Elevated A1c"]
    attrs = json.loads(rows[0]["attrs"])  # roster kept lossless, promoted fields excluded
    assert attrs["a1c"] == 7.0 and "name" not in attrs and "risk" not in attrs


def test_metrics_emit_model_risk_only_when_present():
    base = {"dom": {}, "outcomes": {}, "measures": {}, "needIndex": 50, "hpsaScore": 10, "patients": 1000}
    assert dict(writer._metrics({**base, "modelRisk": 0.7}))["model.risk"] == 0.7
    assert "model.risk" not in dict(writer._metrics(base))
