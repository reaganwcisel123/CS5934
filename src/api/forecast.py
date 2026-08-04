"""Early-warning endpoints: condition forecasts and allocated county warnings (US-052).

Serves from Postgres when DATABASE_URL is set, otherwise computes live from the
model so local dev works without a database, mirroring src/api/atlas.py.
"""

from __future__ import annotations

import functools

from fastapi import APIRouter, HTTPException

from src.api.atlas import load_atlas
from src.db.engine import db_configured
from src.model import forecast_config as FC

router = APIRouter(prefix="/api", tags=["forecast"])


@router.get("/threats")
def threats(top_n: int = 5) -> dict:
    """The conditions running furthest above their seasonal norm in Virginia."""
    from src.model import supply_needs as sn
    from src.model import threat_ranking as tr

    try:
        region = tr.load_region()
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc

    ranked = tr.rank_threats(region, top_n=max(1, min(top_n, 10)))
    supply_map = sn.load_supply_map()

    for row in ranked:
        row["blurb"] = sn.blurb_for(row["condition"], supply_map)
        row["recent_series"] = tr.recent_series(region, row["condition"])

    return {
        "jurisdiction": "Virginia",
        "threats": ranked,
        "method": {
            "recent_weeks": tr.RECENT_WEEKS,
            "baseline": "same MMWR weeks in prior years",
            "baseline_years": tr.BASELINE_YEARS,
            "min_recent_cases": tr.MIN_RECENT_CASES,
            "neighbor_states": [tr._title(n) for n in tr.NEIGHBOR_JURISDICTIONS],
        },
        # Carried on every response so the UI cannot present un-reviewed
        # clinical guidance as settled.
        "clinical_review": sn.review_status(supply_map),
    }


@router.get("/threats/counties/{fips}")
def county_threats(fips: str, top_n: int = 5) -> dict:
    """Top threats with their county-allocated case load and supply estimates.

    Threats are ranked on observed data across all reported conditions, most of
    which are outside the 11-condition forecast set. So the county figure is the
    current observed rate carried over the horizon, not a model forecast, and is
    labelled `projection_basis: observed_rate` to keep the two apart.
    """
    from src.model import supply_needs as sn

    payload = threats(top_n=top_n)
    records = load_atlas()["records"]
    if not any(r["id"] == fips for r in records):
        raise HTTPException(404, f"county {fips} not found")

    share = _share(fips, {r["id"]: float(r.get("patients") or 0) for r in records})
    horizon = FC.HORIZON_WEEKS

    projected = [
        {"condition": t["condition"], "status": "ok",
         "point": round(t["recent_weekly_mean"] * horizon * share, 2),
         # Band from the seasonal baseline up to the current rate, so a county
         # sees the range between "back to normal" and "this keeps up".
         "lower": round(t["seasonal_baseline"] * horizon * share, 2),
         "upper": round(t["recent_weekly_mean"] * horizon * share, 2),
         "horizon_weeks": horizon}
        for t in payload["threats"]
    ]
    supplies = {s["condition"]: s for s in sn.supply_needs(projected)}

    for row, proj in zip(payload["threats"], projected):
        row["county"] = {
            "county_fips": fips,
            "expected_cases": proj["point"],
            "range_low": proj["lower"],
            "range_high": proj["upper"],
            "horizon_weeks": horizon,
            "population_share": round(share, 6),
            "allocation_method": FC.ALLOCATION_METHOD,
            "projection_basis": "observed_rate",
            "is_observed": False,
            "supplies": supplies.get(row["condition"], {}).get("items", []),
        }

    payload["county_fips"] = fips
    payload["allocation_method"] = FC.ALLOCATION_METHOD
    payload["disclosure"] = FC.ALLOCATION_DISCLOSURE
    return payload


@router.get("/forecast")
def forecasts() -> dict:
    """State-level condition forecasts for Virginia."""
    if db_configured():
        from src.db import forecast_queries
        payload = forecast_queries.get_forecasts()
        # The forecast tables are only filled by an explicit loader, so an empty
        # result means "never loaded", not "no data" -- compute live instead.
        if not payload["forecasts"]:
            payload = {"forecasts": _live_forecasts()}
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
            payload = _live_county_warnings(fips)
    else:
        payload = _live_county_warnings(fips)

    # Repeated on every response: a client must never have to infer that these
    # numbers are allocated from state surveillance rather than observed.
    payload["allocation_method"] = FC.ALLOCATION_METHOD
    payload["disclosure"] = FC.ALLOCATION_DISCLOSURE
    return payload


# Cached: the history CSV only changes at deploy, and computing live refits a
# model per condition. Callers copy rows before mutating them.
@functools.lru_cache(maxsize=1)
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
