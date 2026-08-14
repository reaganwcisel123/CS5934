from __future__ import annotations

import json
import os
from pathlib import Path

from src.api import funding


ROOT = Path(__file__).parents[1]
ARTIFACT = ROOT / "dashboard" / "data" / "grant_funding_matches.json"


def test_checked_in_cached_recommendations_are_complete_and_public() -> None:
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    metadata = artifact["metadata"]
    assert metadata["matchingMethod"] == "gemini-prompt-ranking"
    assert metadata["recommendationStatus"] == "current"
    assert len(artifact["profiles"]) == metadata["countyCount"] == 133
    assert len(artifact["opportunities"]) == metadata["opportunityCount"]
    populated = [fips for fips, rows in artifact["matchesByCounty"].items() if rows]
    assert len(populated) == 133
    for fips in populated[:3]:
        for match in artifact["matchesByCounty"][fips]:
            assert match["opportunityId"] in artifact["opportunities"]
            assert match["fitReasons"]
    encoded = json.dumps(artifact)
    assert "GEMINI_API_KEY" not in encoded
    assert "GOOGLE_API_KEY" not in encoded


def test_funding_api_uses_checked_in_cache_without_gemini_or_database(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(funding, "load_last_known_good", lambda: None)
    artifact = funding.funding_matches()
    assert artifact["metadata"]["matchingMethod"] == "gemini-prompt-ranking"
    assert artifact["matchesByCounty"]["51001"]
