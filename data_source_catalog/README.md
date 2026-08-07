# Data Source Catalog

This folder holds the data source catalog: the machine-readable config in
`config/` and the human-readable notes in `docs/`. The point is to make every
data source auditable and reproducible so ingestion code can depend on it.

Ingestion reads this catalog. Each source class in `src/ingestion/` looks up
its entry through the shared loader (`src/catalog.py`), and
`src/build_dataset.py` assembles the dashboard dataset from it. Eight sources
are registered as wired (real or synthetic) in `src/ingestion/registry.py`;
`cdc_nndss` is also real but runs on its own (it is state-keyed and feeds the
forecasting pipeline instead of the county merge), and the Grants.gov corpus
is ingested by `src/grants/pipeline.py`. The rest are catalogued stubs. See
the repo-root `README.md` for how to build and run.

Validate the catalog (from the repo root):

```bash
uv run python data_source_catalog/scripts/validate_data_catalog.py
```

The validator checks both `config/data_sources.yml` (19 sources) and
`config/field_lineage.json` (31 lineage rows): required fields present,
unique `source_id`s, lineage rows pointing at real sources, and no secrets in
`api_key_env_var`.

## How ingestion code should use the catalog

Don't parse the YAML yourself. Import `Catalog` from `src/catalog.py` and read
`access_url`, `documentation_url`, `join_keys`, and `schema_version` from the
matching `source_id`. That keeps URLs and assumptions out of individual
scripts.

## A caution on statuses

Some entries are deliberately marked `needs_verification`, `not_started`, or
`deprecated_or_historical`. Those aren't failures, they're audit flags: they
tell the team which sources need follow-up before production use.
