#!/usr/bin/env python3
"""
Validate the US-006 data source catalog and field lineage files.

Usage:
    python scripts/validate_data_catalog.py

This script validates:
1. Required fields are present for every source.
2. source_id values are unique.
3. Every field-lineage source_id exists in the source catalog.
4. No obvious secret values are committed in api_key_env_var fields.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA_SOURCES_JSON = ROOT / "config" / "data_sources.json"
FIELD_LINEAGE_JSON = ROOT / "config" / "field_lineage.json"

REQUIRED_SOURCE_FIELDS = [
    "source_id",
    "source_name",
    "provider",
    "access_method",
    "access_url",
    "documentation_url",
    "geographic_granularity",
    "refresh_cadence",
    "schema_version",
    "join_keys",
    "fields_used",
    "limitations",
    "privacy_classification",
    "ingestion_status",
    "ingestion_script",
    "last_verified_date",
]

REQUIRED_LINEAGE_FIELDS = [
    "final_field",
    "source_id",
    "original_field",
    "transformation",
    "required_for_mvp",
]

ALLOWED_STATUSES = {
    "not_started",
    "needs_verification",
    "access_verified",
    "schema_reviewed",
    "ingestion_wired",
    "sample_pull_successful",
    "validated",
    "deprecated_or_historical",
}


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_sources(sources: list[dict]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()

    for i, source in enumerate(sources, start=1):
        sid = source.get("source_id", f"<missing:{i}>")

        if sid in seen:
            errors.append(f"Duplicate source_id: {sid}")
        seen.add(sid)

        for field in REQUIRED_SOURCE_FIELDS:
            if field not in source:
                errors.append(f"{sid}: missing required field '{field}'")
            elif source[field] in ("", [], {}):
                errors.append(f"{sid}: required field '{field}' is empty")

        status = source.get("ingestion_status")
        if status and status not in ALLOWED_STATUSES:
            errors.append(f"{sid}: invalid ingestion_status '{status}'")

        # api_key_env_var should contain an environment variable name, not a real token.
        env_value = source.get("api_key_env_var")
        if isinstance(env_value, str):
            suspicious = any(token in env_value.lower() for token in ["bearer ", "secret", "token=", "key=", "password"])
            if suspicious:
                errors.append(f"{sid}: api_key_env_var looks like a secret value; use an env var name only")

    return errors


def validate_lineage(fields: list[dict], valid_source_ids: set[str]) -> list[str]:
    errors: list[str] = []
    seen_fields: set[str] = set()

    for i, field in enumerate(fields, start=1):
        final_field = field.get("final_field", f"<missing:{i}>")

        if final_field in seen_fields:
            errors.append(f"Duplicate final_field in lineage: {final_field}")
        seen_fields.add(final_field)

        for required in REQUIRED_LINEAGE_FIELDS:
            if required not in field:
                errors.append(f"{final_field}: missing required field '{required}'")
            elif field[required] in ("", [], {}):
                errors.append(f"{final_field}: required field '{required}' is empty")

        source_id = field.get("source_id")
        if source_id and source_id not in valid_source_ids:
            errors.append(f"{final_field}: source_id '{source_id}' does not exist in data_sources.json")

    return errors


def main() -> int:
    source_doc = load_json(DATA_SOURCES_JSON)
    lineage_doc = load_json(FIELD_LINEAGE_JSON)

    sources = source_doc.get("sources", [])
    fields = lineage_doc.get("fields", [])

    errors = []
    errors.extend(validate_sources(sources))
    source_ids = {source["source_id"] for source in sources if "source_id" in source}
    errors.extend(validate_lineage(fields, source_ids))

    if errors:
        print("US-006 catalog validation failed:\n")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"US-006 catalog validation passed.")
    print(f"- Sources validated: {len(sources)}")
    print(f"- Field lineage rows validated: {len(fields)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
