# US-006: Author the Data Source Catalog

This folder contains starter files for US-006. The goal is to make every data source auditable and reproducible before ingestion code depends on it.

Since we did this more as a source verification mock and not a fully functional service ingestion scripts aren't included in this PR. If writing those and
building out a pipleine is a future we would want to explore a follow-up story would need to be written up to address. 

```bash
python scripts/validate_data_catalog.py
```

## How ingestion code should use the catalog

Ingestion scripts should load `config/data_sources.yml`, find the matching `source_id`, and use the catalog's `access_url`, `documentation_url`, `join_keys`, and `schema_version`. This prevents URLs and assumptions from being scattered across the codebase.

## Important caution

Some entries are intentionally marked as `needs_verification`, `not_started`, or `deprecated_or_historical`. Those are not failures; they are audit flags. They show the team exactly which sources need follow-up before production use.
