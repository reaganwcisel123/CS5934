"""Shared loader for the data source catalog.

The one place the pipeline reads data_sources.yml and field_lineage.json.
Ingestion, the build, and the validator all import from here so access URLs,
join keys, schema versions, and field provenance live in exactly one place.

Usage:
    from src.catalog import Catalog
    cat = Catalog.load()
    url = cat.source("cdc_places")["access_url"]
"""

from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = REPO_ROOT / "data_source_catalog" / "config"
DATA_SOURCES_YML = CATALOG_DIR / "data_sources.yml"
FIELD_LINEAGE_JSON = CATALOG_DIR / "field_lineage.json"


class Catalog:
    """In-memory view of the catalog and its field lineage."""

    def __init__(self, sources: list[dict], lineage: list[dict]) -> None:
        self._sources = sources
        self._lineage = lineage

    @classmethod
    def load(
        cls,
        sources_path: Path = DATA_SOURCES_YML,
        lineage_path: Path = FIELD_LINEAGE_JSON,
    ) -> "Catalog":
        if not sources_path.exists():
            raise FileNotFoundError(f"Missing catalog file: {sources_path}")
        if not lineage_path.exists():
            raise FileNotFoundError(f"Missing field lineage file: {lineage_path}")
        sources = yaml.safe_load(sources_path.read_text(encoding="utf-8")).get("sources", [])
        lineage = json.loads(lineage_path.read_text(encoding="utf-8")).get("fields", [])
        return cls(sources=sources, lineage=lineage)

    # sources
    @cached_property
    def _by_id(self) -> dict[str, dict]:
        return {s["source_id"]: s for s in self._sources if "source_id" in s}

    @property
    def sources(self) -> list[dict]:
        return self._sources

    def source(self, source_id: str) -> dict:
        try:
            return self._by_id[source_id]
        except KeyError:
            raise KeyError(f"source_id '{source_id}' not in {DATA_SOURCES_YML.name}") from None

    def access_url(self, source_id: str) -> str:
        return self.source(source_id)["access_url"]

    # field lineage
    @property
    def lineage(self) -> list[dict]:
        return self._lineage

    @cached_property
    def _lineage_by_field(self) -> dict[str, dict]:
        return {r["final_field"]: r for r in self._lineage if "final_field" in r}

    def lineage_for(self, final_field: str) -> dict | None:
        return self._lineage_by_field.get(final_field)

    def has_lineage(self, final_field: str) -> bool:
        return final_field in self._lineage_by_field

    def mvp_fields(self) -> list[str]:
        return [r["final_field"] for r in self._lineage if r.get("required_for_mvp")]
