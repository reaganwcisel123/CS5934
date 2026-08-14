"""Serve a durable Funding Matches snapshot without exposing Gemini internals."""

import json

from fastapi import APIRouter, HTTPException

from src.catalog import REPO_ROOT
from src.grants.storage import load_last_known_good

router = APIRouter(prefix="/api", tags=["funding"])
FALLBACK = REPO_ROOT / "dashboard" / "data" / "grant_funding_matches.json"


def _is_gemini_snapshot(artifact: dict | None) -> bool:
    metadata = artifact.get("metadata") if isinstance(artifact, dict) else None
    return isinstance(metadata, dict) and metadata.get("matchingMethod") == "gemini-prompt-ranking"


@router.get("/funding-matches")
def funding_matches() -> dict:
    persisted = load_last_known_good()
    if FALLBACK.exists():
        fallback = json.loads(FALLBACK.read_text(encoding="utf-8"))
        if _is_gemini_snapshot(persisted) or not _is_gemini_snapshot(fallback):
            return persisted or fallback
        return fallback
    if persisted:
        return persisted
    raise HTTPException(503, "Funding Matches has no current recommendation snapshot.")
