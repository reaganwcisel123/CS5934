from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from src.grants.client import GrantsGovClient
from src.grants.normalize import (
    clean_text,
    is_healthcare_relevant,
    is_open_or_forecasted,
    normalize_many,
    parse_date,
    parse_number,
)

FIXTURE = Path(__file__).parent / "fixtures" / "grants_gov_opportunities.json"


def _records() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["records"]


def test_cleaners_handle_html_dates_and_currency() -> None:
    assert clean_text("<p>Rural&nbsp;health<br>access</p>") == "Rural health\naccess"
    assert parse_date("Aug 12, 2026 12:00:00 AM EDT") == "2026-08-12"
    assert parse_date("not a date") is None
    assert parse_number("$1,188,684") == 1188684
    assert parse_number(None) is None


def test_normalization_retains_canonical_fields_and_missing_values() -> None:
    opportunities, metrics = normalize_many(_records(), retrieved_at="2026-08-04T00:00:00Z")
    behavioral = next(item for item in opportunities if item["opportunity_id"] == "rural-behavioral")
    assert behavioral["closing_date"] == "2026-12-15"
    assert behavioral["applicant_types"]
    assert behavioral["award_floor"] == 100000
    assert behavioral["official_url"].endswith("rural-behavioral")
    assert metrics["raw_result_count"] == 5
    assert metrics["missing_award_range_rate"] > 0


def test_status_and_relevance_rules_do_not_recommend_closed_or_arts_records() -> None:
    opportunities, _ = normalize_many(_records(), retrieved_at="2026-08-04T00:00:00Z")
    closed = next(item for item in opportunities if item["opportunity_id"] == "closed-health")
    arts = next(item for item in opportunities if item["opportunity_id"] == "arts")
    assert not is_open_or_forecasted(closed, today=date(2026, 8, 4))
    assert not is_healthcare_relevant(arts)


def test_fixture_mode_is_offline_and_deterministic() -> None:
    records, metadata = GrantsGovClient().retrieve(fixture_path=FIXTURE)
    assert len(records) == 5
    assert metadata["cache"] == "fixture"
