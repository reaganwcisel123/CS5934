from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest

pytest.importorskip("sklearn")

from src.grants.normalize import normalize_many
from src.grants.pipeline import build_artifact
from src.grants.profiles import build_profile
from src.grants.recommender import GrantRecommender, candidate_opportunities, evaluation_metrics

FIXTURE = Path(__file__).parent / "fixtures" / "grants_gov_opportunities.json"
TODAY = date(2026, 8, 4)


def _opportunities() -> list[dict]:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))["records"]
    opportunities, _ = normalize_many(raw, retrieved_at="2026-08-04T00:00:00Z")
    return opportunities


def _county(**overrides) -> dict:
    county = {
        "id": "51001", "name": "Fixture County", "region": "Tidewater", "rural": 1.0,
        "needIndex": 74.0, "hpsaScore": 18.0,
        "dom": {"food": 72.0, "access": 82.0, "economic": 70.0, "environment": 40.0},
        "outcomes": {"diabetes": 13.0, "obesity": 38.0, "mhlth": 26.0, "bphigh": 37.0},
    }
    county.update(overrides)
    return county


def test_profile_generation_is_controlled_and_traceable() -> None:
    profile = build_profile(_county())
    tags = {item["tag"] for item in profile["profileTags"]}
    assert "rural_healthcare_delivery" in tags
    assert "primary_care_workforce_shortage" in tags
    assert all(item["sourceField"] and item["thresholdRule"] for item in profile["profileTags"])
    assert "not a confirmed clinic strategy" in profile["profileText"]


def test_behavioral_profile_ranks_behavioral_grant_above_workforce_grant() -> None:
    candidates = candidate_opportunities(_opportunities(), today=TODAY)
    profile = build_profile(_county(hpsaScore=0.0))
    matches = GrantRecommender().fit(candidates).recommend(profile, today=TODAY)
    ids = [match["opportunityId"] for match in matches]
    assert ids.index("rural-behavioral") < ids.index("workforce")


def test_workforce_profile_ranks_workforce_grant_and_excludes_hard_mismatches() -> None:
    candidates = candidate_opportunities(_opportunities(), today=TODAY)
    ids = {item["opportunity_id"] for item in candidates}
    assert "closed-health" not in ids
    assert "incompatible-geo" not in ids
    profile = build_profile(_county(outcomes={"diabetes": 0, "obesity": 0, "mhlth": 0, "bphigh": 0}, dom={"food": 0, "access": 0, "economic": 0, "environment": 0}))
    matches = GrantRecommender().fit(candidates).recommend(profile, today=TODAY)
    assert matches[0]["opportunityId"] == "workforce"


def test_scores_explanations_and_evaluation_are_bounded_and_deterministic() -> None:
    candidates = candidate_opportunities(_opportunities(), today=TODAY)
    profile = build_profile(_county())
    recommender = GrantRecommender().fit(candidates)
    first = recommender.recommend(profile, today=TODAY)
    second = recommender.recommend(profile, today=TODAY)
    assert first == second
    assert all(0.0 <= match["matchScore"] <= 1.0 for match in first)
    assert all(match["fitReasons"] and match["readinessChecklist"] for match in first)
    metrics = evaluation_metrics(_opportunities(), candidates, {"51001": first}, today=TODAY)
    assert 0.0 <= metrics["validOpportunityRate"] <= 1.0
    assert metrics["officialLinkValidityRate"] == 1.0


def test_pipeline_artifact_is_compact_json_with_all_county_profiles(tmp_path: Path) -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))["records"]
    atlas = {"records": [_county(), _county(id="51003", name="Second Fixture County")]}
    artifact = build_artifact(
        atlas,
        raw,
        source_retrieved_at="2026-08-04T00:00:00Z",
        cache_status="fixture",
        model_directory=tmp_path / "model",
        today=TODAY,
    )
    encoded = json.dumps(artifact, allow_nan=False)
    assert artifact["metadata"]["countyCount"] == 2
    assert set(artifact["matchesByCounty"]) == {"51001", "51003"}
    assert "description" in artifact["opportunities"]["workforce"]
    assert "description" not in artifact["matchesByCounty"]["51001"][0]
    assert encoded
