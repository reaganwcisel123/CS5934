"""Persist condition forecasts and county warnings (US-052).

Separate module from writer.py so the forecasting epic does not touch the
atlas write path.
"""

from __future__ import annotations

import json

from sqlalchemy import text

from src.db.engine import get_engine

_UPSERT_FORECAST = text(
    "insert into condition_forecast(as_of,condition,status,horizon_weeks,point_estimate,"
    "lower_bound,upper_bound,as_of_year,as_of_week,weeks_stale,model_version) "
    "values(current_date,:condition,:status,:horizon,:point,:lower,:upper,"
    ":as_of_year,:as_of_week,:stale,:version) "
    "on conflict(condition,as_of,horizon_weeks) do update set "
    "status=excluded.status,point_estimate=excluded.point_estimate,"
    "lower_bound=excluded.lower_bound,upper_bound=excluded.upper_bound,"
    "as_of_year=excluded.as_of_year,as_of_week=excluded.as_of_week,"
    "weeks_stale=excluded.weeks_stale,model_version=excluded.model_version"
)

_UPSERT_WARNING = text(
    "insert into county_condition_warning(as_of,county_fips,condition,allocated_point,"
    "allocated_lower,allocated_upper,population_share,allocation_method,supplies) "
    "values(current_date,:fips,:condition,:point,:lower,:upper,:share,:method,cast(:supplies as jsonb)) "
    "on conflict(county_fips,condition,as_of) do update set "
    "allocated_point=excluded.allocated_point,allocated_lower=excluded.allocated_lower,"
    "allocated_upper=excluded.allocated_upper,population_share=excluded.population_share,"
    "allocation_method=excluded.allocation_method,supplies=excluded.supplies"
)


def forecast_rows(forecasts: list[dict], model_version: str = "") -> list[dict]:
    return [
        {"condition": f["condition"], "status": f.get("status", "ok"),
         "horizon": f.get("horizon_weeks"), "point": f.get("point"),
         "lower": f.get("lower"), "upper": f.get("upper"),
         "as_of_year": f.get("as_of_year"), "as_of_week": f.get("as_of_week"),
         "stale": f.get("weeks_stale"), "version": model_version}
        for f in forecasts
    ]


def warning_rows(warnings: list[dict]) -> list[dict]:
    rows = []
    for w in warnings:
        if not w.get("allocation_method"):
            raise ValueError(
                f"{w.get('county_fips')}/{w.get('condition')}: allocation_method is required; "
                "an allocated county figure must say how it was derived"
            )
        rows.append({
            "fips": w["county_fips"], "condition": w["condition"],
            "point": w.get("allocated_point"), "lower": w.get("allocated_lower"),
            "upper": w.get("allocated_upper"), "share": w.get("population_share"),
            "method": w["allocation_method"],
            "supplies": json.dumps(w.get("supplies") or []),
        })
    return rows


def load_forecasts(forecasts: list[dict], model_version: str = "") -> int:
    rows = forecast_rows(forecasts, model_version)
    if rows:
        with get_engine().begin() as c:
            c.execute(_UPSERT_FORECAST, rows)
    return len(rows)


def load_warnings(warnings: list[dict]) -> int:
    rows = warning_rows(warnings)
    if rows:
        with get_engine().begin() as c:
            c.execute(_UPSERT_WARNING, rows)
    return len(rows)
