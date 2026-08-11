from __future__ import annotations

from datetime import date
from copy import deepcopy
import json
from pathlib import Path

from src.grants.client import GrantsGovClient
from src.grants.normalize import (
    clean_text,
    is_healthcare_relevant,
    is_open_or_forecasted,
    is_within_lookback,
    normalize_many,
    parse_date,
    parse_number,
    write_normalized_cache,
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


def test_publisher_placeholder_zero_award_amounts_remain_unavailable() -> None:
    records = deepcopy(_records())
    records[0]["detail"]["synopsis"]["awardFloor"] = "0"
    records[0]["detail"]["synopsis"]["awardCeiling"] = "0"
    opportunities, _ = normalize_many(records, retrieved_at="2026-08-04T00:00:00Z")
    behavioral = next(item for item in opportunities if item["opportunity_id"] == "rural-behavioral")
    assert behavioral["award_floor"] is None
    assert behavioral["award_ceiling"] is None


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


def test_client_scope_keeps_relevant_health_and_community_agencies() -> None:
    assert GrantsGovClient._allowed_agency({"agencyCode": "HHS-HRSA"})
    assert GrantsGovClient._allowed_agency({"agencyCode": "USDA-RUS"})
    assert GrantsGovClient._allowed_agency({"agencyCode": "DOL-ETA"})
    assert not GrantsGovClient._allowed_agency({"agencyCode": "NEA"})


def test_lookback_boundary_is_inclusive_and_uses_posting_date() -> None:
    opportunity, _ = normalize_many(_records()[:1], retrieved_at="2026-08-04T00:00:00Z")
    item = opportunity[0]
    item["posting_date"] = "2026-07-28"
    assert is_within_lookback(item, today=date(2026, 8, 4), days=7)
    item["posting_date"] = "2026-07-27"
    assert not is_within_lookback(item, today=date(2026, 8, 4), days=7)


def test_client_paginates_every_page_and_deduplicates_hits(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("src.grants.client.C.SEARCH_TERMS", ("health",))

    class PagedClient(GrantsGovClient):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[int] = []

        def search(self, keyword: str, *, start_record: int = 0, rows: int = 10) -> dict:
            self.calls.append(start_record)
            pages = {
                0: [{"id": "one", "agencyCode": "HHS"}, {"id": "two", "agencyCode": "HHS"}],
                2: [{"id": "two", "agencyCode": "HHS"}, {"id": "three", "agencyCode": "HHS"}],
                4: [{"id": "four", "agencyCode": "HHS"}],
            }
            return {"data": {"oppHits": pages[start_record], "hitCount": 5}}

        def fetch_detail(self, opportunity_id: str) -> dict:
            return {"data": {"id": opportunity_id}}

    client = PagedClient()
    records, metadata = client.retrieve(refresh=True, cache_path=tmp_path / "raw.json")
    assert client.calls == [0, 2, 4]
    assert [record["detail"]["id"] for record in records] == ["four", "one", "three", "two"]
    assert metadata["search_pages"] == 3


def test_processed_cache_is_separate_from_raw_fixture(tmp_path: Path) -> None:
    opportunities, metrics = normalize_many(_records(), retrieved_at="2026-08-04T00:00:00Z")
    path = tmp_path / "normalized.json"
    write_normalized_cache(opportunities, metrics, retrieved_at="2026-08-04T00:00:00Z", path=path)
    cached = json.loads(path.read_text(encoding="utf-8"))
    assert cached["records"][0]["opportunity_id"]
    assert cached["quality"]["normalized_record_count"] == 5
