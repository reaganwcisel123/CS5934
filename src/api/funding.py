"""Serve a durable Funding Matches snapshot without exposing Gemini internals."""

import json

from fastapi import APIRouter, HTTPException

from src.catalog import REPO_ROOT
from src.grants.storage import load_last_known_good

router = APIRouter(prefix="/api", tags=["funding"])
FALLBACK = REPO_ROOT / "dashboard" / "data" / "grant_funding_matches.json"


@router.get("/funding-matches")
def funding_matches() -> dict:
    artifact = load_last_known_good()
    if artifact:
        return artifact
    if FALLBACK.exists():
        return json.loads(FALLBACK.read_text(encoding="utf-8"))
    raise HTTPException(503, "Funding Matches has no current recommendation snapshot.")
