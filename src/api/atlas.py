"""Load the atlas from Postgres when configured, else the built static JSON (dev)."""

from __future__ import annotations

import json

from fastapi import HTTPException

from src.catalog import REPO_ROOT
from src.db.engine import db_configured

JSON_FALLBACK = REPO_ROOT / "dashboard" / "data" / "clinic_atlas.json"


def load_atlas() -> dict:
    if db_configured():
        from src.db import queries
        return queries.get_atlas()
    if JSON_FALLBACK.exists():
        return json.loads(JSON_FALLBACK.read_text(encoding="utf-8"))
    raise HTTPException(503, "No DATABASE_URL and no clinic_atlas.json fallback available.")


def get_county(fips: str) -> dict | None:
    return next((r for r in load_atlas()["records"] if r["id"] == fips), None)
