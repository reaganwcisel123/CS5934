"""Read forecasts and county warnings back out of Postgres (US-052)."""

from __future__ import annotations

from sqlalchemy import text

from src.db.engine import get_engine


def get_forecasts() -> dict:
    """Latest state-level forecast per condition."""
    with get_engine().connect() as c:
        rows = c.execute(text(
            "select condition,status,horizon_weeks,point_estimate,lower_bound,upper_bound,"
            "as_of_year,as_of_week,weeks_stale,model_version from condition_forecast "
            "where as_of=(select max(as_of) from condition_forecast) order by condition"
        )).mappings().all()

    return {"forecasts": [
        {"condition": r["condition"], "status": r["status"],
         "horizon_weeks": r["horizon_weeks"],
         "point": _num(r["point_estimate"]), "lower": _num(r["lower_bound"]),
         "upper": _num(r["upper_bound"]), "as_of_year": r["as_of_year"],
         "as_of_week": r["as_of_week"], "weeks_stale": r["weeks_stale"],
         "model_version": r["model_version"]}
        for r in rows
    ]}


def get_county_warnings(fips: str) -> dict:
    """Allocated warnings for one county, newest vintage."""
    with get_engine().connect() as c:
        rows = c.execute(text(
            "select condition,allocated_point,allocated_lower,allocated_upper,"
            "population_share,allocation_method,supplies from county_condition_warning "
            "where county_fips=:fips and as_of=(select max(as_of) from county_condition_warning) "
            "order by allocated_point desc nulls last"
        ), {"fips": fips}).mappings().all()

    return {
        "county_fips": fips,
        "warnings": [
            {"condition": r["condition"], "point": _num(r["allocated_point"]),
             "lower": _num(r["allocated_lower"]), "upper": _num(r["allocated_upper"]),
             "population_share": _num(r["population_share"]),
             "allocation_method": r["allocation_method"],
             "is_observed": False,
             "supplies": r["supplies"] or []}
            for r in rows
        ],
    }


def _num(v):
    return float(v) if v is not None else None
