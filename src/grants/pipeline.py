"""CLI pipeline for the independent Grants.gov rural clinic recommender."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any

from src.catalog import REPO_ROOT
from src.grants import config as C
from src.grants.client import GrantsGovClient
from src.grants.normalize import normalize_many, write_normalized_cache
from src.grants.profiles import build_profiles
from src.grants.recommender import GrantRecommender, candidate_opportunities, evaluation_metrics


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


def build_artifact(
    atlas: dict[str, Any], raw_records: list[dict[str, Any]], *, source_retrieved_at: str, cache_status: str,
    model_directory: Path = C.MODEL_ARTIFACT_DIR, normalized_cache_path: Path | None = None, today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    opportunities, quality = normalize_many(raw_records, retrieved_at=source_retrieved_at)
    if normalized_cache_path:
        write_normalized_cache(opportunities, quality, retrieved_at=source_retrieved_at, path=normalized_cache_path)
    candidates = candidate_opportunities(opportunities, today=today)
    if not candidates:
        raise ValueError("No active, healthcare-relevant Grants.gov opportunities remain after filtering.")
    profiles = build_profiles(atlas.get("records") or [])
    recommender = GrantRecommender().fit(candidates)
    matches_by_county = {county_id: recommender.recommend(profile, today=today) for county_id, profile in profiles.items()}
    model_metadata = recommender.save(model_directory, source_retrieved_at=source_retrieved_at)
    evaluation = evaluation_metrics(opportunities, candidates, matches_by_county, today=today)
    return {
        "metadata": {
            "generatedAt": _now(), "source": "Grants.gov", "sourceUrl": C.SOURCE_DOCUMENTATION_URL,
            "sourceRetrievedAt": source_retrieved_at, "cacheStatus": cache_status, "modelVersion": C.MODEL_VERSION,
            "opportunityCount": len(candidates), "countyCount": len(profiles), "topRecommendations": C.TOP_RECOMMENDATIONS,
            "quality": quality, "evaluation": evaluation, "model": model_metadata,
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
    parser.add_argument("--model-dir", type=Path, default=C.MODEL_ARTIFACT_DIR, help="Ignored fitted model artifact directory.")
    args = parser.parse_args(argv)
    atlas_path = REPO_ROOT / "dashboard" / "data" / "clinic_atlas.json"
    atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
    raw_records, retrieval = GrantsGovClient().retrieve(refresh=args.refresh, max_results=args.max_results, fixture_path=args.fixture)
    source_retrieved_at = retrieval["retrieved_at"] if retrieval["retrieved_at"] != "fixture" else "fixture"
    artifact = build_artifact(
        atlas,
        raw_records,
        source_retrieved_at=source_retrieved_at,
        cache_status=retrieval["cache"],
        model_directory=args.model_dir,
        normalized_cache_path=C.NORMALIZED_CACHE_PATH,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Built {args.output} with {artifact['metadata']['opportunityCount']} opportunities and {artifact['metadata']['countyCount']} county profiles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
