"""Predictive Analytics epic: the resource-prediction API endpoints."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi", reason="needs `uv sync --extra api`")

from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402

client = TestClient(app)


def test_resource_prediction_endpoints_are_registered():
    paths = app.openapi()["paths"]

    assert "/api/resource-predictions/counties/{fips}" in paths
    assert "/api/resource-predictions/counties/{fips}/export" in paths


def test_county_prediction_endpoint_returns_a_categorized_plan():
    response = client.get("/api/resource-predictions/counties/51001?window=30")

    assert response.status_code == 200
    body = response.json()
    assert body["county_fips"] == "51001"
    assert body["planning_window_days"] == 30
    assert body["status"] == "ok"
    for category in ("medications", "medical_supplies", "diagnostic_equipment", "staffing"):
        assert body[category]


def test_prediction_endpoint_404s_for_an_unknown_county():
    response = client.get("/api/resource-predictions/counties/99999?window=30")

    assert response.status_code == 404


def test_prediction_endpoint_422s_for_an_unconfigured_window():
    response = client.get("/api/resource-predictions/counties/51001?window=45")

    assert response.status_code == 422


def test_prediction_defaults_to_a_30_day_window():
    response = client.get("/api/resource-predictions/counties/51001")

    assert response.status_code == 200
    assert response.json()["planning_window_days"] == 30


def test_csv_export_has_the_right_content_type_and_filename():
    response = client.get("/api/resource-predictions/counties/51001/export?window=60&format=csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="resource-plan-51001-60d.csv"' in response.headers["content-disposition"]
    assert response.text.startswith("county_fips,")


def test_json_export_has_the_right_content_type():
    response = client.get("/api/resource-predictions/counties/51001/export?window=30&format=json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["county_fips"] == "51001"


def test_export_422s_on_an_unsupported_format():
    response = client.get("/api/resource-predictions/counties/51001/export?window=30&format=xml")

    assert response.status_code == 422


def test_export_404s_for_an_unknown_county():
    response = client.get("/api/resource-predictions/counties/99999/export?window=30&format=csv")

    assert response.status_code == 404
