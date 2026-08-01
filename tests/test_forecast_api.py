"""US-052: forecast persistence rows and the early-warning API."""

from __future__ import annotations

import json

import pytest

from src.db import forecast_writer as fw
from src.model import forecast_config as FC

fastapi = pytest.importorskip("fastapi", reason="needs `uv sync --extra api`")

from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402

client = TestClient(app)


# --- writer row shaping ------------------------------------------------------

def test_forecast_rows_carry_the_model_version():
    rows = fw.forecast_rows(
        [{"condition": "Pertussis", "status": "ok", "horizon_weeks": 4, "point": 3.0,
          "lower": 1.0, "upper": 9.0, "as_of_year": 2026, "as_of_week": 20, "weeks_stale": 0}],
        model_version="v1",
    )

    assert rows[0]["version"] == "v1"
    assert rows[0]["horizon"] == 4


def test_insufficient_history_forecasts_still_persist():
    # Absence of a forecast is itself information; dropping the row would make
    # the condition look untracked instead of unforecastable.
    rows = fw.forecast_rows(
        [{"condition": "Mumps", "status": "insufficient_history", "horizon_weeks": 4}])

    assert rows[0]["status"] == "insufficient_history"
    assert rows[0]["point"] is None


def test_warning_rows_serialize_supplies_as_json():
    rows = fw.warning_rows([{
        "county_fips": "51001", "condition": "Pertussis", "allocated_point": 0.4,
        "allocated_lower": 0.1, "allocated_upper": 1.2, "population_share": 0.004,
        "allocation_method": FC.ALLOCATION_METHOD,
        "supplies": [{"item": "N95 respirator", "quantity_high": 8}],
    }])

    assert json.loads(rows[0]["supplies"])[0]["item"] == "N95 respirator"


def test_warning_row_without_an_allocation_method_is_rejected():
    # The schema's not-null is backed here so the failure names the county.
    with pytest.raises(ValueError, match="allocation_method is required"):
        fw.warning_rows([{"county_fips": "51001", "condition": "Pertussis",
                          "allocated_point": 1.0, "allocation_method": ""}])


# --- API ---------------------------------------------------------------------

def test_forecast_endpoint_reports_jurisdiction_and_horizon():
    response = client.get("/api/forecast")

    assert response.status_code in (200, 503)
    if response.status_code == 200:
        body = response.json()
        assert body["jurisdiction"] == "Virginia"
        assert body["horizon_weeks"] == FC.HORIZON_WEEKS


def test_forecast_endpoint_is_registered():
    # Included routers do not expand into app.routes; the OpenAPI schema is the
    # canonical registry of mounted paths.
    paths = app.openapi()["paths"]

    assert "/api/forecast" in paths
    assert "/api/forecast/counties/{fips}" in paths


def test_county_endpoint_404s_for_an_unknown_county():
    response = client.get("/api/forecast/counties/99999")

    assert response.status_code in (404, 503)


def test_health_still_responds_after_mounting_the_router():
    assert client.get("/api/health").status_code == 200


def test_threat_endpoints_are_registered():
    paths = app.openapi()["paths"]

    assert "/api/threats" in paths
    assert "/api/threats/counties/{fips}" in paths


def test_threats_response_carries_its_method_and_review_status():
    response = client.get("/api/threats?top_n=3")

    assert response.status_code in (200, 503)
    if response.status_code == 200:
        body = response.json()
        assert body["method"]["baseline"] == "same MMWR weeks in prior years"
        assert len(body["method"]["neighbor_states"]) == 6
        # Un-reviewed clinical guidance must announce itself on every payload.
        assert body["clinical_review"]["clinical_review"] == "pending"


def test_threats_top_n_is_clamped():
    response = client.get("/api/threats?top_n=999")

    if response.status_code == 200:
        assert len(response.json()["threats"]) <= 10


def test_county_threats_label_their_basis_as_observed_rate(monkeypatch):
    # Threats span conditions outside the forecast set, so the county number is
    # the current rate carried forward, not a model forecast. Conflating the two
    # would overstate what the model actually claims.
    from src.api import forecast as api_forecast

    monkeypatch.setattr(api_forecast, "load_atlas", lambda: {"records": [
        {"id": "51001", "patients": 20_000}, {"id": "51003", "patients": 80_000},
    ]})
    monkeypatch.setattr(api_forecast, "threats", lambda top_n=5: {
        "threats": [{"condition": "Pertussis", "recent_weekly_mean": 10.0,
                     "seasonal_baseline": 4.0}]})

    body = api_forecast.county_threats("51001", top_n=1)
    county = body["threats"][0]["county"]

    assert county["projection_basis"] == "observed_rate"
    assert county["is_observed"] is False
    assert county["allocation_method"] == FC.ALLOCATION_METHOD
    # 10/wk * 4 weeks * 20% share = 8
    assert county["expected_cases"] == pytest.approx(8.0)
    assert county["range_low"] == pytest.approx(3.2)


def test_county_threats_404_on_an_unknown_county(monkeypatch):
    from src.api import forecast as api_forecast

    monkeypatch.setattr(api_forecast, "load_atlas", lambda: {"records": [{"id": "51001", "patients": 1}]})
    monkeypatch.setattr(api_forecast, "threats", lambda top_n=5: {"threats": []})

    with pytest.raises(Exception):
        api_forecast.county_threats("99999")


def test_county_supplies_are_sized_from_the_allocated_share(monkeypatch):
    # Regression: supplies were sized off the state forecast and attached to
    # county rows, telling one county to stock for all of Virginia.
    from src.api import forecast as api_forecast

    monkeypatch.setattr(api_forecast, "load_atlas", lambda: {"records": [
        {"id": "51001", "patients": 10_000}, {"id": "51003", "patients": 90_000},
    ]})
    monkeypatch.setattr(api_forecast, "_live_forecasts", lambda: [
        {"condition": "Pertussis", "status": "ok", "point": 100.0, "lower": 80.0,
         "upper": 120.0, "horizon_weeks": 4, "weeks_stale": 0},
    ])

    small = api_forecast._live_county_warnings("51001")["warnings"][0]
    large = api_forecast._live_county_warnings("51003")["warnings"][0]

    assert small["point"] == pytest.approx(10.0)   # 10% of 100
    assert large["point"] == pytest.approx(90.0)

    swab_small = next(i for i in small["supplies"] if "PCR" in i["item"])
    swab_large = next(i for i in large["supplies"] if "PCR" in i["item"])
    assert swab_small["quantity_expected"] < swab_large["quantity_expected"]
