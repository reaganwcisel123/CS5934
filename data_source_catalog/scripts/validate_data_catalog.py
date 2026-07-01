#!/usr/bin/env python3
"""
Validate the data source catalog and field lineage files.

Usage (from the repo root):
    uv run python data_source_catalog/scripts/validate_data_catalog.py

This script validates:
1. Required fields are present for every source.
2. source_id values are unique.
3. Every field-lineage source_id exists in the source catalog.
4. No obvious secret values are committed in api_key_env_var fields.
"""

from __future__ import annotations

from pathlib import Path
import sys

# Import the shared catalog loader (src/catalog.py) so this validator reads the
# exact same YAML/JSON the ingestion code does: one loader, one source of truth.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from src.catalog import Catalog  # noqa: E402

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
            errors.append(f"{final_field}: source_id '{source_id}' does not exist in data_sources.yml")

    return errors


def main() -> int:
    catalog = Catalog.load()
    sources = catalog.sources
    fields = catalog.lineage

    errors = []
    errors.extend(validate_sources(sources))
    source_ids = {source["source_id"] for source in sources if "source_id" in source}
    errors.extend(validate_lineage(fields, source_ids))

    if errors:
        print("Catalog validation failed:\n")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Catalog validation passed.")
    print(f"- Sources validated: {len(sources)}")
    print(f"- Field lineage rows validated: {len(fields)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
