# Installation and Configuration Guide

This guide is the reproducible clean-machine setup for the Clinic Needs Atlas.
It covers three supported run modes:

1. Static dashboard backed by generated JSON.
2. FastAPI backed by the generated JSON fallback.
3. Full PostgreSQL-backed platform with authentication and model scores.

The project uses public county-level data and deterministic synthetic patient
records. Do not add PHI, real patient identifiers, or production EHR exports.

## 1. Prerequisites

Required:

- Git.
- macOS, Linux, or Windows Subsystem for Linux.
- Outbound HTTPS access for dependency installation and public data downloads.
- `uv` for Python, virtual environments, and locked dependencies.

Install `uv` on macOS or Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

The repository requires Python 3.11 or newer. `uv` installs a compatible Python
interpreter when necessary.

Optional:

- PostgreSQL 14 or newer for the complete database-backed platform.
- Census API key for reliable ACS and population retrieval.
- Anthropic API key for the chatbot.

## 2. Clone and install

```bash
git clone https://github.com/reaganwcisel123/CS5934.git
cd CS5934
git checkout develop
```

Confirm that the commands are being run from the repository root:

```bash
ls README.md pyproject.toml uv.lock
```

Install the complete development environment:

```bash
uv sync --frozen --extra api --extra model
```

`--frozen` requires the exact dependency resolution committed in `uv.lock` and
prevents an installation from silently rewriting the lock file. The virtual
environment is created at `.venv/`; manual activation is not required.

Optional dependency groups:

| Group | Purpose | Command |
|---|---|---|
| Core | Ingestion and transforms | `uv sync --frozen` |
| API | FastAPI, PostgreSQL, authentication, and chatbot client | `uv sync --frozen --extra api` |
| Model | scikit-learn and joblib | `uv sync --frozen --extra model` |
| Email | Google survey-outreach tools | `uv sync --frozen --extra email` |

## 3. Configure the environment

Create the local configuration file:

```bash
cp .env.example .env
```

Populate only the variables required for the selected run mode:

| Variable | Required when | Purpose |
|---|---|---|
| `CENSUS_API_KEY` | Recommended for refreshed builds | Census ACS and county population retrieval. |
| `DATABASE_URL` | Using PostgreSQL | Database connection for migrations, loading, authentication, and API queries. |
| `JWT_SECRET` | Using authentication | Signs JWT session tokens. |
| `ANTHROPIC_API_KEY` | Using the chatbot | Enables `POST /api/chat`. |
| `ATLAS_CHAT_MODEL` | Optional | Overrides the configured chatbot model. |
| `ATLAS_CHAT_RATE_MAX` | Optional | Questions allowed per rate-limit window. |
| `ATLAS_CHAT_RATE_WINDOW` | Optional | Rate-limit window in seconds. |

Generate a JWT secret:

```bash
uv run --frozen python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`scripts/run-pipeline.sh` and `scripts/verify-install.sh` automatically load
`.env`. For an individual command, use `--env-file .env` with `uv run`.

Never commit `.env`. Rotate any database credential or API key that appears in
chat, screenshots, tickets, or logs.

## 4. Mode A: static dashboard without PostgreSQL

Build the dashboard dataset:

```bash
./scripts/run-pipeline.sh
```

With no `DATABASE_URL`, this command:

1. Installs the locked core dependencies.
2. Refreshes available public sources.
3. Uses documented placeholders for unavailable sources.
4. Writes `dashboard/data/clinic_atlas.json`.

Serve the repository over HTTP:

```bash
uv run --frozen python -m http.server 8000
```

Open:

```text
http://localhost:8000/dashboard/
```

Do not open the dashboard through `file://`; the page loads its dataset through
`fetch()` and therefore requires an HTTP server.

## 5. Mode B: FastAPI with JSON fallback

Complete Mode A first so `dashboard/data/clinic_atlas.json` exists.

Start the API in one terminal:

```bash
uv run --frozen --env-file .env uvicorn src.api.main:app --reload --port 8001
```

Start the static server in another terminal:

```bash
uv run --frozen python -m http.server 8000
```

Open the dashboard in API mode:

```text
http://localhost:8000/dashboard/clinic-needs-atlas-signal.html?api=http://localhost:8001/api
```

Useful endpoints:

```text
http://localhost:8001/api/health
http://localhost:8001/api/counties
http://localhost:8001/api/sources
http://localhost:8001/docs
```

Without `DATABASE_URL`, the expected health response is:

```json
{"status":"ok","db":false}
```

Authentication requires PostgreSQL. The chatbot may run without PostgreSQL when
`ANTHROPIC_API_KEY` is set, but usage is not tied to a persisted user account.

## 6. Mode C: complete PostgreSQL platform

Create a PostgreSQL database locally or use the external connection URL from
Render. Add the connection and JWT secret to `.env`:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/clinic_atlas
JWT_SECRET=replace-with-a-long-random-secret
```

Run the complete pipeline:

```bash
./scripts/run-pipeline.sh
```

When `DATABASE_URL` is set, the script:

1. Installs the locked API and model dependencies.
2. Applies `db/migrations/*.sql` in order.
3. Seeds source and field-lineage metadata.
4. Refreshes the county and synthetic-patient dataset.
5. Trains the county and patient models.
6. Scores counties and patients.
7. Upserts the resulting records into PostgreSQL.

Start the API:

```bash
uv run --frozen --env-file .env uvicorn src.api.main:app --reload --port 8001
```

The expected health response is:

```json
{"status":"ok","db":true}
```

Serve the dashboard in a second terminal:

```bash
uv run --frozen python -m http.server 8000
```

Open the authenticated local dashboard:

```text
http://localhost:8000/dashboard/clinic-needs-atlas-signal.html?api=http://localhost:8001/api&auth=1
```

The migrations currently create a demonstration-only account:

```text
Email: demo@clinicatlas.dev
Password: triad-demo-2026
```

Replace or remove this account before production use.

## 7. Data access and cache behavior

Source URLs, ownership, update cadence, and implementation status are defined in:

```text
data_source_catalog/config/data_sources.yml
```

Field-level lineage is defined in:

```text
data_source_catalog/config/field_lineage.json
```

The active ingestion registry is:

```text
src/ingestion/registry.py
```

A refreshed build requires outbound HTTPS access to the configured Census, CDC,
HRSA, USDA, EPA, and HUD sources. Network errors, missing credentials, and
unavailable sources are reported as warnings. The dashboard build continues with
provenance-labeled placeholders when possible.

Raw downloads are cached in:

```text
data/raw/
```

Use cache files when available:

```bash
uv run --frozen --env-file .env python src/build_dataset.py
```

Force current upstream downloads:

```bash
uv run --frozen --env-file .env python src/build_dataset.py --refresh
```

The software environment is reproducible through `uv.lock`. Public datasets can
change between refresh dates, so exact data reproduction also depends on the
cached raw files and the provenance recorded in the generated output.

## 8. Model commands

Train both models:

```bash
./scripts/train-model.sh
```

Train one model:

```bash
uv run --frozen python -m src.model.train --target county
uv run --frozen python -m src.model.train --target patient
```

Attach model risk tiers and drivers to the generated JSON:

```bash
uv run --frozen --env-file .env python src/build_dataset.py --score
```

Score and load PostgreSQL:

```bash
uv run --frozen --env-file .env python src/build_dataset.py --score --to-db
```

County model training requires usable county outcomes and SDoH features. If all
live sources are unavailable, the fallback dashboard can still build, but the
county model cannot train from placeholder-only rows.

Generated model files:

```text
models/county_model.joblib
models/county_metrics.json
models/patient_model.joblib
models/patient_metrics.json
```

## 9. Validation and clean-machine verification

Run all tests:

```bash
uv run --frozen pytest
```

Run architecture contracts:

```bash
uv run --frozen lint-imports
```

Validate the data catalog:

```bash
uv run --frozen python data_source_catalog/scripts/validate_data_catalog.py
```

Run the automated installation verification:

```bash
./scripts/verify-install.sh
```

Force fresh upstream downloads:

```bash
./scripts/verify-install.sh --refresh
```

Include model training and scoring:

```bash
./scripts/verify-install.sh --full --refresh
```

Verify the PostgreSQL path:

```bash
./scripts/verify-install.sh --with-db --refresh
```

`--with-db` requires `DATABASE_URL`, implies `--full`, applies migrations, and
writes to the configured database.

A successful run ends with:

```text
Installation verification passed.
```

## 10. Generated paths

| Path | Generated by | Committed? |
|---|---|---:|
| `.venv/` | `uv sync` | No |
| `data/raw/*` | Ingestion sources | No |
| `dashboard/data/clinic_atlas.json` | Dataset build | No |
| `models/*` | Model training | No |
| PostgreSQL tables | Migrations and writers | External |

The committed reconstruction inputs are `pyproject.toml`, `uv.lock`, source
code, source catalog, database migrations, reference data, and deterministic
synthetic-data logic.

## 11. Troubleshooting

### `uv: command not found`

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Dashboard cannot load data

Confirm the generated file exists and serve the repository over HTTP:

```bash
ls -lh dashboard/data/clinic_atlas.json
uv run --frozen python -m http.server 8000
```

### Census fields remain placeholders

Add `CENSUS_API_KEY` to `.env` and rerun:

```bash
./scripts/verify-install.sh --refresh
```

### API reports `db: false`

Confirm `DATABASE_URL` is populated and start Uvicorn with `--env-file .env`.

### Authentication returns 503

Authentication requires PostgreSQL and applied migrations. Run the full pipeline
with `DATABASE_URL` configured.

### Chatbot returns 503

Set `ANTHROPIC_API_KEY` and restart the API. The chatbot is optional.

### Model training reports insufficient rows or one target class

Review the source warnings and provenance. Restore network access or required
credentials and rerun the build with `--refresh`.
