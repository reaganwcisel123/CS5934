# Data Source Catalog

This folder contains the data source catalog. The goal is to make every data source auditable and reproducible so ingestion code can depend on it.

Ingestion now reads this catalog: each source in `src/ingestion/` looks up its entry here, and `src/build_dataset.py` assembles the dashboard dataset from it. Six sources are wired to real/synthetic data; the rest remain catalogued stubs. See the repo-root `README.md` for how to build and run.

Validate the catalog (from the repo root):

```bash
uv run python data_source_catalog/scripts/validate_data_catalog.py
```

## How ingestion code should use the catalog

Ingestion scripts should load `config/data_sources.yml`, find the matching `source_id`, and use the catalog's `access_url`, `documentation_url`, `join_keys`, and `schema_version`. This prevents URLs and assumptions from being scattered across the codebase.

## Important caution

Some entries are intentionally marked as `needs_verification`, `not_started`, or `deprecated_or_historical`. Those are not failures; they are audit flags. They show the team exactly which sources need follow-up before production use.
