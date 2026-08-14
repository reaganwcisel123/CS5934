"""Small, cache-aware client for the public Grants.gov opportunity APIs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.grants import config as C

LOG = logging.getLogger(__name__)


class GrantsGovError(RuntimeError):
    """A clear error from the public Grants.gov service or its payload."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


class GrantsGovClient:
    """Retrieve the complete configured public opportunity scope with a local cache."""

    def __init__(
        self,
        *,
        timeout: int = C.REQUEST_TIMEOUT_SECONDS,
        retries: int = C.REQUEST_RETRIES,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = timeout
        self.session = session or requests.Session()
        retry = Retry(
            total=retries,
            backoff_factor=0.4,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"POST"}),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "ClinicNeedsAtlas/1.0 (+public Grants.gov planning recommender)",
        })

    def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise GrantsGovError(f"Grants.gov request failed for {url}: {exc}") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise GrantsGovError("Grants.gov returned a non-JSON response.") from exc
        if body.get("errorcode") not in (None, 0):
            raise GrantsGovError(f"Grants.gov API error: {body.get('msg') or body.get('errorcode')}")
        if not isinstance(body.get("data"), dict):
            raise GrantsGovError("Grants.gov response has no object-valued data field.")
        return body

    def search(self, *, start_record: int = 0, rows: int = C.PAGE_SIZE) -> dict[str, Any]:
        """Search every posted opportunity without topic, agency, or category filters."""
        return self._post(C.SEARCH_ENDPOINT, {
            "rows": rows,
            "keyword": C.SEARCH_KEYWORD,
            "oppStatuses": "|".join(C.ALLOWED_STATUSES),
            "startRecordNum": start_record,
            "eligibilities": "",
            "agencies": "",
            "fundingCategories": "",
            "fundingInstruments": "",
            "aln": "",
        })

    def fetch_detail(self, opportunity_id: str) -> dict[str, Any]:
        """Fetch one current opportunity detail record with `fetchOpportunity`."""
        return self._post(C.DETAIL_ENDPOINT, {"opportunityId": str(opportunity_id)})

    def _cache_is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        age = _utc_now() - datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return age <= timedelta(hours=C.CACHE_FRESHNESS_HOURS)

    @staticmethod
    def _read_payload(path: Path) -> list[dict[str, Any]]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
        records = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise GrantsGovError(f"Local source {path} must contain a list or an object with records.")
        return records

    @staticmethod
    def _write_cache(records: list[dict[str, Any]], path: Path, retrieved_at: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "retrieved_at": retrieved_at,
            "source_urls": [C.SEARCH_ENDPOINT, C.DETAIL_ENDPOINT],
            "records": records,
        }, indent=2, sort_keys=True), encoding="utf-8")

    def retrieve(
        self,
        *,
        refresh: bool = False,
        max_results: int = C.MAX_RESULTS,
        fixture_path: Path | None = None,
        cache_path: Path = C.RAW_CACHE_PATH,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Return detail/search pairs from a fixture, fresh cache, or public API.

        The cache stores only response data, never the ephemeral token field sent by
        the API, and is intentionally kept under the repository's ignored raw data.
        """
        if fixture_path:
            records = self._read_payload(fixture_path)
            return records, {"retrieved_at": "fixture", "cache": "fixture"}
        if not refresh and self._cache_is_fresh(cache_path):
            return self._read_payload(cache_path), {"retrieved_at": "cache", "cache": "fresh"}

        hits: dict[str, dict[str, Any]] = {}
        searches = 0
        start = 0
        while True:
            body = self.search(start_record=start)
            searches += 1
            data = body["data"]
            page_hits = data.get("oppHits") or []
            if not isinstance(page_hits, list):
                raise GrantsGovError("Grants.gov search2 response has an invalid oppHits field.")
            for hit in page_hits:
                opportunity_id = str(hit.get("id") or "")
                if opportunity_id:
                    hits.setdefault(opportunity_id, hit)
                    if max_results and len(hits) >= max_results:
                        break
            start += len(page_hits)
            hit_count = int(data.get("hitCount") or 0)
            if not page_hits or start >= hit_count or (max_results and len(hits) >= max_results):
                break

        retrieved_at = _iso_now()
        records = []
        for opportunity_id, hit in hits.items():
            detail = self.fetch_detail(opportunity_id)["data"]
            records.append({"search_hit": hit, "detail": detail})
        records.sort(key=lambda record: str(record["search_hit"].get("id") or ""))
        self._write_cache(records, cache_path, retrieved_at)
        LOG.info("Retrieved %s Grants.gov details from %s search pages.", len(records), searches)
        return records, {"retrieved_at": retrieved_at, "cache": "refreshed", "search_pages": searches}
