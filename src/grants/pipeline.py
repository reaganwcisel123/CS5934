"""CLI pipeline for the independent Grants.gov rural clinic recommender."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from src.catalog import REPO_ROOT
from src.grants import config as C
from src.grants.client import GrantsGovClient
from src.grants.normalize import normalize_many, write_normalized_cache
from src.grants.profiles import build_profiles
from src.grants.gemini import FixtureGeminiRanker, GeminiRanker, GeminiRankingError, RankingClient, model_name
from src.grants.recommender import candidate_opportunities, evaluation_metrics, rank_profiles
from src.grants.storage import load_last_known_good, save_snapshot


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _opportunity_for_dashboard(opportunity: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": opportunity["title"], "opportunityNumber": opportunity["opportunity_number"],
        "agencyCode": opportunity["agency_code"], "agency": opportunity["agency_name"],
        "status": opportunity["status"], "synopsis": opportunity["synopsis"],
        "description": opportunity["description"], "applicantTypes": opportunity["applicant_types"],
        "eligibilityDescription": opportunity["eligibility_description"], "fundingCategories": opportunity["funding_categories"],
        "fundingInstruments": opportunity["funding_instruments"], "assistanceListingNumbers": opportunity["assistance_listing_numbers"],
        "postingDate": opportunity["posting_date"], "openingDate": opportunity["opening_date"], "closingDate": opportunity["closing_date"],
        "archiveDate": opportunity["archive_date"], "awardFloor": opportunity["award_floor"], "awardCeiling": opportunity["award_ceiling"],
        "estimatedTotalFunding": opportunity["estimated_total_funding"], "expectedAwardCount": opportunity["expected_award_count"],
        "costSharingRequired": opportunity["cost_sharing_required"], "officialUrl": opportunity["official_url"],
    }


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _model_metadata(*, source_retrieved_at: str, corpus_hash: str, profile_hash: str) -> dict[str, Any]:
    return {"modelVersion": C.MODEL_VERSION, "matchingMethod": "gemini-prompt-ranking", "geminiModel": model_name(), "promptVersion": C.GEMINI_PROMPT_VERSION, "candidateLimit": C.GEMINI_CANDIDATE_LIMIT, "profileBatchSize": C.GEMINI_PROFILE_BATCH_SIZE, "sourceRetrievedAt": source_retrieved_at, "corpusHash": corpus_hash, "profileHash": profile_hash}


def build_artifact(
    atlas: dict[str, Any], raw_records: list[dict[str, Any]], *, source_retrieved_at: str, cache_status: str,
    model_directory: Path = C.MODEL_ARTIFACT_DIR, normalized_cache_path: Path | None = None, today: date | None = None,
    ranker: RankingClient | None = None, previous_artifact: dict[str, Any] | None = None, force_rerank: bool = False,
) -> dict[str, Any]:
    today = today or date.today()
    opportunities, quality = normalize_many(raw_records, retrieved_at=source_retrieved_at)
    if normalized_cache_path:
        write_normalized_cache(opportunities, quality, retrieved_at=source_retrieved_at, path=normalized_cache_path)
    candidates = candidate_opportunities(opportunities, today=today)
    if not candidates:
        raise ValueError("No active, healthcare-relevant Grants.gov opportunities remain after filtering.")
    profiles = build_profiles(atlas.get("records") or [])
    corpus_hash = _hash(candidates)
    profile_hash = _hash(profiles)
    model_metadata = _model_metadata(source_retrieved_at=source_retrieved_at, corpus_hash=corpus_hash, profile_hash=profile_hash)
    old_meta = (previous_artifact or {}).get("metadata", {}).get("model", {})
    unchanged = not force_rerank and old_meta.get("corpusHash") == corpus_hash and old_meta.get("profileHash") == profile_hash and old_meta.get("geminiModel") == model_metadata["geminiModel"] and old_meta.get("promptVersion") == C.GEMINI_PROMPT_VERSION
    if unchanged and previous_artifact and previous_artifact.get("matchesByCounty"):
        matches_by_county = previous_artifact["matchesByCounty"]
        model_metadata["reusedLastKnownGood"] = True
    else:
        try:
            matches_by_county = rank_profiles(profiles, candidates, ranker=ranker or GeminiRanker(), today=today)
        except GeminiRankingError:
            if not previous_artifact or not previous_artifact.get("matchesByCounty"):
                raise
            matches_by_county = previous_artifact["matchesByCounty"]
            model_metadata["reusedLastKnownGood"] = True
            model_metadata["generationStatus"] = "degraded-last-known-good"
    model_directory.mkdir(parents=True, exist_ok=True)
    (model_directory / "metadata.json").write_text(json.dumps(model_metadata, indent=2, sort_keys=True), encoding="utf-8")
    evaluation = evaluation_metrics(opportunities, candidates, matches_by_county, today=today)
    return {
        "metadata": {
            "generatedAt": _now(), "source": "Grants.gov", "sourceUrl": C.SOURCE_DOCUMENTATION_URL,
            "sourceRetrievedAt": source_retrieved_at, "cacheStatus": cache_status, "modelVersion": C.MODEL_VERSION,
            "opportunityCount": len(candidates), "countyCount": len(profiles), "topRecommendations": C.TOP_RECOMMENDATIONS,
            "quality": quality, "evaluation": evaluation, "model": model_metadata,
            "matchingMethod": "gemini-prompt-ranking", "recommendationStatus": model_metadata.get("generationStatus", "current"),
        },
        "opportunities": {item["opportunity_id"]: _opportunity_for_dashboard(item) for item in candidates},
        "profiles": profiles,
        "matchesByCounty": matches_by_county,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the independent rural clinic grant funding recommender artifacts.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the public Grants.gov raw cache before building.")
    parser.add_argument("--fixture", type=Path, help="Use a local response fixture instead of the network.")
    parser.add_argument("--max-results", type=int, default=C.MAX_RESULTS, help="Maximum targeted opportunity details to retrieve.")
    parser.add_argument("--output", type=Path, default=C.DASHBOARD_ARTIFACT_PATH, help="Dashboard JSON output path.")
    parser.add_argument("--atlas", type=Path, help="Atlas JSON input; defaults to dashboard/data/clinic_atlas.json.")
    parser.add_argument("--model-dir", type=Path, default=C.MODEL_ARTIFACT_DIR, help="Ignored fitted model artifact directory.")
    parser.add_argument("--force-rerank", action="store_true", help="Ignore matching hashes and request a fresh Gemini ranking.")
    parser.add_argument("--daily", action="store_true", help="Run the idempotent daily refresh behavior.")
    parser.add_argument("--persist", action="store_true", help="Promote the validated artifact to configured Postgres storage.")
    args = parser.parse_args(argv)
    atlas_path = args.atlas or REPO_ROOT / "dashboard" / "data" / "clinic_atlas.json"
    if not atlas_path.exists():
        parser.error(f"Atlas input is missing: {atlas_path}. Build the Atlas first or pass --atlas.")
    atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
    raw_records, retrieval = GrantsGovClient().retrieve(refresh=args.refresh, max_results=args.max_results, fixture_path=args.fixture)
    source_retrieved_at = retrieval["retrieved_at"] if retrieval["retrieved_at"] != "fixture" else "fixture"
    previous = load_last_known_good() if args.persist else None
    if args.output.exists():
        try:
            previous = json.loads(args.output.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            previous = None
    # Fixture mode is explicit test behavior; normal runs never fall back to
    # the retired TF-IDF path when Gemini is unavailable.
    ranker = FixtureGeminiRanker() if args.fixture else None
    artifact = build_artifact(
        atlas,
        raw_records,
        source_retrieved_at=source_retrieved_at,
        cache_status=retrieval["cache"],
        model_directory=args.model_dir,
        normalized_cache_path=C.NORMALIZED_CACHE_PATH, ranker=ranker,
        previous_artifact=previous, force_rerank=args.force_rerank,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, allow_nan=False), encoding="utf-8")
    if args.persist:
        save_snapshot(artifact)
    print(f"Built {args.output} with {artifact['metadata']['opportunityCount']} opportunities and {artifact['metadata']['countyCount']} county profiles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
