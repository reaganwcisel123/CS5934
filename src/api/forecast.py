"""Early-warning endpoints: condition forecasts and allocated county warnings (US-052).

Serves from Postgres when DATABASE_URL is set, otherwise computes live from the
model so local dev works without a database, mirroring src/api/atlas.py.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api.atlas import load_atlas
from src.db.engine import db_configured
from src.model import forecast_config as FC

router = APIRouter(prefix="/api", tags=["forecast"])


@router.get("/forecast")
def forecasts() -> dict:
    """State-level condition forecasts for Virginia."""
    if db_configured():
        from src.db import forecast_queries
        payload = forecast_queries.get_forecasts()
    else:
        payload = {"forecasts": _live_forecasts()}

    payload["jurisdiction"] = "Virginia"
    payload["horizon_weeks"] = FC.HORIZON_WEEKS
    return payload


@router.get("/forecast/counties/{fips}")
def county_warnings(fips: str) -> dict:
    """Allocated warnings and supply estimates for one county."""
    if db_configured():
        from src.db import forecast_queries
        payload = forecast_queries.get_county_warnings(fips)
        if not payload["warnings"]:
            raise HTTPException(404, f"no warnings for county {fips}")
    else:
        payload = _live_county_warnings(fips)

    # Repeated on every response: a client must never have to infer that these
    # numbers are allocated from state surveillance rather than observed.
    payload["allocation_method"] = FC.ALLOCATION_METHOD
    payload["disclosure"] = FC.ALLOCATION_DISCLOSURE
    return payload


def _live_forecasts() -> list[dict]:
    from src.model import forecast as fc
    try:
        return fc.forecast_conditions()
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc


def _live_county_warnings(fips: str) -> dict:
    from src.model import forecast_dataset as fd
    from src.model import supply_needs as sn

    records = load_atlas()["records"]
    if not any(r["id"] == fips for r in records):
        raise HTTPException(404, f"county {fips} not found")

    populations = {r["id"]: float(r.get("patients") or 0) for r in records}
    share = _share(fips, populations)

    # Allocate first, then size supplies off the county's share. Sizing from the
    # state forecast would tell one county to stock for all of Virginia.
    allocated = [
        {**f,
         "point": round(f["point"] * share, 2),
         "lower": round(f["lower"] * share, 2),
         "upper": round(f["upper"] * share, 2)}
        for f in _live_forecasts() if f.get("status") == "ok"
    ]
    supplies_by_condition = {s["condition"]: s for s in sn.supply_needs(allocated)}

    warnings = [
        {"condition": f["condition"], "point": f["point"], "lower": f["lower"],
         "upper": f["upper"], "population_share": round(share, 6),
         "allocation_method": FC.ALLOCATION_METHOD, "is_observed": False,
         "weeks_stale": f.get("weeks_stale"),
         "supplies": supplies_by_condition.get(f["condition"], {}).get("items", [])}
        for f in allocated
    ]

    warnings.sort(key=lambda w: w["point"], reverse=True)
    return {"county_fips": fips, "warnings": warnings}


def _share(fips: str, populations: dict[str, float]) -> float:
    total = sum(populations.values())
    if total <= 0:
        raise HTTPException(503, "county populations unavailable; rebuild the atlas")
    return populations.get(fips, 0.0) / total
