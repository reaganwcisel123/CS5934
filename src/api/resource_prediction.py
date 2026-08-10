"""Resource-demand prediction endpoints (Predictive Analytics epic).

Computed live from the atlas JSON, mirroring src/api/forecast.py's no-DB-required
pattern: this module has no Postgres table of its own, so there is nothing to
seed before it works in local dev.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Response

from src.api.atlas import load_atlas
from src.model import resource_prediction as rp

router = APIRouter(prefix="/api", tags=["resource-prediction"])


@router.get("/resource-predictions/counties/{fips}")
def county_resource_prediction(fips: str, window: int = 30) -> dict:
    """Categorized medication/supply/equipment/staffing prediction for one county."""
    return _predict(fips, window)


@router.get("/resource-predictions/counties/{fips}/export")
def export_county_resource_prediction(fips: str, window: int = 30, format: str = "csv") -> Response:
    fmt = format.lower()
    if fmt not in ("csv", "json"):
        raise HTTPException(422, "format must be 'csv' or 'json'")

    prediction = _predict(fips, window)
    filename = f"resource-plan-{fips}-{window}d.{fmt}"

    if fmt == "csv":
        body = rp.to_export_csv(prediction)
        media_type = "text/csv"
    else:
        body = json.dumps(prediction, indent=2)
        media_type = "application/json"

    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _predict(fips: str, window: int) -> dict:
    cfg = rp.load_config()
    if window not in cfg["planning_windows_days"]:
        allowed = ", ".join(str(w) for w in cfg["planning_windows_days"])
        raise HTTPException(422, f"window must be one of: {allowed}")

    records = load_atlas()["records"]
    county = next((r for r in records if r["id"] == fips), None)
    if county is None:
        raise HTTPException(404, f"county {fips} not found")

    state_summary = rp.state_summary(records, config=cfg)
    return rp.predict_resources(county, window, config=cfg, state_summary=state_summary)
