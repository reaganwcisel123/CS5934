# CS5934 — Clinic Needs Atlas

A catalog-driven data pipeline that turns public health data sources into the
**Clinic Needs Atlas** dashboard, plus a survey **email pipeline**.

## Repository layout

| Path | What it is |
|---|---|
| `data_source_catalog/` | Data source catalog: the single source of truth (`config/data_sources.yml`, `config/field_lineage.json`) and its validator. |
| `src/` | Catalog-driven ETL: per-source ingestion (`src/ingestion/`), transforms (`src/transform/`), and the build orchestrator (`src/build_dataset.py`). |
| `dashboard/` | `clinic-needs-atlas.html` (frozen synthetic template) and `clinic-needs-atlas-live.html` (loads real data from `dashboard/data/clinic_atlas.json`). |
| `email_pipeline/` | Survey outreach pipeline (ingest → send → track → follow-up → report). |
| `data/` | `reference/` lookups (committed) and `raw/` cached source extracts (git-ignored). |

## Environment setup (uv)

Dependencies are managed with [uv](https://docs.astral.sh/uv/). `pyproject.toml`
+ `uv.lock` are the canonical, reproducible source of truth.

```bash
uv sync                 # create .venv and install the data-pipeline dependencies
uv sync --extra email   # also install the email pipeline's Google API stack
```

Run anything inside the environment with `uv run`, e.g. `uv run python ...`
(no manual venv activation needed).

## Build the dashboard dataset

A free **Census API key** unlocks the ACS/population sources (economic/education
domains + county population). Copy the example env file and fill it in:

```bash
cp .env.example .env         # then add your CENSUS_API_KEY (see the file for the link)
```

```bash
uv run --env-file .env python src/build_dataset.py --refresh  # re-fetch from upstream APIs
uv run python src/build_dataset.py                            # uses cached raw extracts in data/raw/
```

Without a key the Census sources stay stubbed; everything else (CDC PLACES,
HRSA, USDA) works keyless.

This writes `dashboard/data/clinic_atlas.json` (Virginia counties) and prints,
per field group, whether the data is **real / synthetic / stub**.

## View the dashboard

The live dashboard uses `fetch()`, so it must be served over HTTP (not `file://`):

```bash
uv run python -m http.server 8000
# open http://localhost:8000/dashboard/clinic-needs-atlas-live.html
```

## Validate the catalog

```bash
uv run python data_source_catalog/scripts/validate_data_catalog.py
```

## Data source status

Six sources are wired to real/synthetic data; the rest are catalogued **stubs**
(`StubSource` subclasses in `src/ingestion/`) for another contributor to promote
to `RealSource`. See `src/ingestion/registry.py` for the full list.
