"""Reviewable defaults for the Grants.gov rural-health recommender."""

from __future__ import annotations

from pathlib import Path

from src.catalog import REPO_ROOT

API_BASE_URL = "https://api.grants.gov/v1/api"
SEARCH_ENDPOINT = f"{API_BASE_URL}/search2"
DETAIL_ENDPOINT = f"{API_BASE_URL}/fetchOpportunity"
OFFICIAL_RECORD_URL = "https://www.grants.gov/search-results-detail/{opportunity_id}"
SOURCE_DOCUMENTATION_URL = "https://www.grants.gov/api/api-guide"

CACHE_DIR = REPO_ROOT / "data" / "raw" / "grants_gov_opportunities"
RAW_CACHE_PATH = CACHE_DIR / "raw_opportunities.json"
NORMALIZED_CACHE_PATH = CACHE_DIR / "normalized_opportunities.json"
DEFAULT_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "grants_gov_opportunities.json"

REQUEST_TIMEOUT_SECONDS = 25
REQUEST_RETRIES = 2
CACHE_FRESHNESS_HOURS = 24
PAGE_SIZE = 10
MAX_RESULTS = 60
MIN_DAYS_REMAINING = 1

# HHS includes HRSA and CDC. USDA is intentionally limited to Rural Development
# subagencies so the planning corpus does not become a broad agriculture search.
ALLOWED_AGENCY_PREFIXES = ("HHS", "USDA-RBCS", "USDA-RUS", "USDA-RD")
ALLOWED_STATUSES = ("posted", "forecasted")
SEARCH_TERMS = (
    "rural health",
    "primary care",
    "behavioral health",
    "telehealth",
    "health workforce",
    "chronic disease",
    "maternal health",
    "community health",
)
HEALTHCARE_RELEVANCE_TERMS = (
    "rural", "health", "healthcare", "health care", "clinic", "primary care",
    "behavioral", "mental health", "telehealth", "workforce", "diabetes",
    "hypertension", "obesity", "maternal", "community health", "mobile health",
    "prevention", "care access", "health equity", "quality improvement",
)

MODEL_VERSION = "grant-recommender-v1"
MODEL_ARTIFACT_DIR = REPO_ROOT / "models" / "grant_recommender"
DASHBOARD_ARTIFACT_PATH = REPO_ROOT / "dashboard" / "data" / "grant_funding_matches.json"

TFIDF_PARAMETERS = {
    "lowercase": True,
    "stop_words": "english",
    "ngram_range": (1, 2),
    "min_df": 1,
    "max_df": 1.0,
    "max_features": 2000,
    "sublinear_tf": True,
}
SCORE_WEIGHTS = {
    "semantic": 0.75,
    "category": 0.10,
    "eligibility": 0.10,
    "deadline": 0.05,
}
TOP_RECOMMENDATIONS = 10

# Values use the Atlas's existing 0--100 domain scale and published outcome
# percentages. They are deliberately centralized, deterministic, and reviewable.
PROFILE_THRESHOLDS = {
    "rural": 0.5,
    "hpsa_score": 14,
    "access_burden": 60,
    "economic_burden": 65,
    "food_burden": 60,
    "environment_burden": 70,
    "need_index": 65,
    "diabetes": 11,
    "obesity": 35,
    "mental_distress": 20,
    "hypertension": 34,
}
