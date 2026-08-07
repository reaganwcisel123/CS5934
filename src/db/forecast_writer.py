"""Row-shaping for condition forecasts and county warnings (US-052).

Separate module from writer.py so the forecasting epic does not touch the
atlas write path. The API computes forecasts live; these shapers feed any
future persistence step.
"""

from __future__ import annotations

import json


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
