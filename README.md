# CS5934: Clinic Needs Atlas

A catalog-driven data pipeline that turns public health data sources into the
**Clinic Needs Atlas** dashboard, plus a survey **email pipeline**.

## Repository layout

| Path | What it is |
|---|---|
| `data_source_catalog/` | The data source catalog, our single source of truth (`config/data_sources.yml`, `config/field_lineage.json`), plus its validator. |
| `src/` | Catalog-driven ETL: per-source ingestion (`src/ingestion/`), transforms (`src/transform/`), and the build orchestrator (`src/build_dataset.py`). |
| `dashboard/` | `index.html` (public landing) and `app.html` (the Signal app: one shell, hash-routed views in `dashboard/app/`, loads real data from `dashboard/data/clinic_atlas.json`). |
| `reference/` | Frozen early dashboard prototypes (`clinic-needs-atlas.html`, `-live.html`) kept for design reference; not deployed. |
| `email_pipeline/` | Survey outreach pipeline (ingest → send → track → follow-up → report). |
| `data/` | `reference/` lookups and the `synthetic/` clinical CSV (committed); `raw/` cached source extracts and `processed/` surveillance history (git-ignored). |

## Environment setup (uv)

Dependencies are managed with [uv](https://docs.astral.sh/uv/); `pyproject.toml`
and `uv.lock` pin the environment.

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

Without a key the Census sources stay stubbed. CDC PLACES, HRSA, USDA, and the
Virginia chronic-disease source are keyless, and the EJI environment domain
reads from a committed reference file, so all of those work without any setup.

This writes `dashboard/data/clinic_atlas.json` (Virginia counties) and prints,
per field group, whether the data is **real / synthetic / stub**.

## Reproduce everything (one command)

`scripts/run-pipeline.sh` regenerates all results from the catalog in one step.
It's essentially what Render runs on deploy (Render also runs the NNDSS
ingestion for the forecast routes):

```bash
./scripts/run-pipeline.sh                        # build the dashboard dataset (JSON only)
DATABASE_URL=postgresql://… ./scripts/run-pipeline.sh   # also migrate + seed + train + load Postgres
```

With no `DATABASE_URL` it installs deps and rebuilds `clinic_atlas.json`. With
one set, it also applies migrations, seeds the catalog, trains and scores both
risk models, and loads counties + patients into Postgres. The script reads
`.env`, so set `CENSUS_API_KEY` there to unlock the ACS economic/education
panels.

## View the dashboard

The live dashboard uses `fetch()`, so it must be served over HTTP (not `file://`):

```bash
uv run python -m http.server 8000
# open http://localhost:8000/dashboard/app.html
```

## Validate the catalog

```bash
uv run python data_source_catalog/scripts/validate_data_catalog.py
```

## Data source status

Eight sources are wired to real or synthetic data. The other nine registered
sources are catalogued **stubs** (`StubSource` subclasses in
`src/ingestion/stubs.py`) waiting for a contributor to promote them to
`RealSource`. See `src/ingestion/registry.py` for the full list.
