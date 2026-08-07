# Installation and Configuration Guide

Clean-machine setup for the Clinic Needs Atlas. There are three supported ways
to run it:

1. Static dashboard backed by generated JSON.
2. FastAPI backed by the generated JSON fallback.
3. Full PostgreSQL-backed platform with authentication and model scores.

The project uses public county-level data and deterministic synthetic patient
records. Do not add PHI, real patient identifiers, or production EHR exports.

## 1. Prerequisites

You need git, outbound HTTPS (for dependency installs and public data
downloads), and [uv](https://docs.astral.sh/uv/), which handles Python
versions, virtual environments, and locked dependencies. The helper scripts are
bash, so on Windows use WSL.

Install `uv` on macOS or Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

The repository requires Python 3.11 or newer; `uv` will install a compatible
interpreter if you don't have one.

Optional, depending on the run mode:

- PostgreSQL 14 or newer (Mode C).
- A Census API key, for reliable ACS and population retrieval.
- An Anthropic API key, for the chatbot.

## 2. Clone and install

```bash
git clone https://github.com/reaganwcisel123/CS5934.git
cd CS5934
git checkout develop
```

Make sure you're at the repository root:

```bash
ls README.md pyproject.toml uv.lock
```

Install the full development environment:

```bash
uv sync --frozen --extra api --extra model
```

`--frozen` installs the exact resolution committed in `uv.lock` instead of
silently rewriting the lock file. The virtual environment lands in `.venv/`;
you never need to activate it manually (use `uv run`).

Optional dependency groups:

| Group | Purpose | Command |
|---|---|---|
| Core | Ingestion and transforms | `uv sync --frozen` |
| API | FastAPI, PostgreSQL, authentication, and chatbot client | `uv sync --frozen --extra api` |
| Model | scikit-learn and joblib | `uv sync --frozen --extra model` |
| Email | Google survey-outreach tools | `uv sync --frozen --extra email` |

## 3. Configure the environment

```bash
cp .env.example .env
```

Fill in only what your run mode needs:

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

`scripts/run-pipeline.sh` and `scripts/verify-install.sh` load `.env` on their
own. For an individual command, pass `--env-file .env` to `uv run`.

Never commit `.env`. If a database credential or API key ends up in chat,
screenshots, tickets, or logs, rotate it.

## 4. Mode A: static dashboard without PostgreSQL

Build the dashboard dataset:

```bash
./scripts/run-pipeline.sh
```

With no `DATABASE_URL`, this installs the locked core dependencies, refreshes
whatever public sources are reachable, falls back to documented placeholders
for the rest, and writes `dashboard/data/clinic_atlas.json`.

Serve the repository over HTTP:

```bash
uv run --frozen python -m http.server 8000
```

Then open:

```text
http://localhost:8000/dashboard/
```

Don't open the dashboard via `file://`; the page loads its dataset with
`fetch()`, which needs an HTTP server.

## 5. Mode B: FastAPI with JSON fallback

Do Mode A first so `dashboard/data/clinic_atlas.json` exists.

Start the API in one terminal:

```bash
uv run --frozen --env-file .env uvicorn src.api.main:app --reload --port 8001
```

Start the static server in another:

```bash
uv run --frozen python -m http.server 8000
```

Open the dashboard in API mode:

```text
http://localhost:8000/dashboard/app.html?api=http://localhost:8001/api
```

Useful endpoints:

```text
http://localhost:8001/api/health
http://localhost:8001/api/counties
http://localhost:8001/api/sources
http://localhost:8001/docs
```

Without `DATABASE_URL`, the health endpoint should return:

```json
{"status":"ok","db":false}
```

Authentication requires PostgreSQL. The chatbot works without PostgreSQL as
long as `ANTHROPIC_API_KEY` is set, but usage isn't tied to a persisted user
account.

## 6. Mode C: complete PostgreSQL platform

Create a PostgreSQL database locally, or use the external connection URL from
Render. Add the connection and JWT secret to `.env`:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/clinic_atlas
JWT_SECRET=replace-with-a-long-random-secret
```

Run the full pipeline:

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

Health should now report:

```json
{"status":"ok","db":true}
```

Serve the dashboard in a second terminal:

```bash
uv run --frozen python -m http.server 8000
```

Open the authenticated local dashboard:

```text
http://localhost:8000/dashboard/app.html?api=http://localhost:8001/api&auth=1
```

The migrations create a demonstration-only account:

```text
Email: demo@clinicatlas.dev
Password: triad-demo-2026
```

Replace or remove it before production use.

## 7. Data access and cache behavior

Source URLs, ownership, update cadence, and implementation status live in
`data_source_catalog/config/data_sources.yml`. Field-level lineage is in
`data_source_catalog/config/field_lineage.json`. The active ingestion registry
is `src/ingestion/registry.py`.

A refreshed build needs outbound HTTPS to the configured Census, CDC, HRSA,
USDA, and data.virginia.gov endpoints (the EJI environment domain reads a
committed reference file, so it works offline). Network errors, missing
credentials, and unavailable sources are reported as warnings; the build
continues with provenance-labeled placeholders when it can.

Raw downloads are cached in `data/raw/`.

Use cache files when available:

```bash
uv run --frozen --env-file .env python src/build_dataset.py
```

Force current upstream downloads:

```bash
uv run --frozen --env-file .env python src/build_dataset.py --refresh
```

The software environment is reproducible through `uv.lock`. Public datasets
change between refresh dates, though, so reproducing exact data also depends on
the cached raw files and the provenance recorded in the generated output.

## 8. Model commands

Train both models:

```bash
./scripts/train-model.sh
```

Or train one:

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

County model training needs usable county outcomes and SDoH features. If every
live source is unavailable, the fallback dashboard still builds, but the county
model can't train from placeholder-only rows.

Generated model files:

```text
models/county_model.joblib
models/county_metrics.json
models/patient_model.joblib
models/patient_metrics.json
```

## 9. Validation and clean-machine verification

Run the tests, the architecture contracts, and the catalog validator:

```bash
uv run --frozen pytest
uv run --frozen lint-imports
uv run --frozen python data_source_catalog/scripts/validate_data_catalog.py
```

Automated installation verification:

```bash
./scripts/verify-install.sh                   # dashboard + JSON API fallback
./scripts/verify-install.sh --refresh         # force fresh upstream downloads
./scripts/verify-install.sh --full --refresh  # also train and score both models
./scripts/verify-install.sh --with-db --refresh   # PostgreSQL path
```

`--with-db` requires `DATABASE_URL`, implies `--full`, applies migrations, and
writes to the configured database.

A successful run ends with:

```text
==> Installation verification passed.
```

## 10. Generated paths

| Path | Generated by | Committed? |
|---|---|---:|
| `.venv/` | `uv sync` | No |
| `data/raw/*` | Ingestion sources | No |
| `dashboard/data/clinic_atlas.json` | Dataset build | Not intended (in `.gitignore`, but currently still tracked) |
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

Check that the generated file exists and serve the repository over HTTP:

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

Check that `DATABASE_URL` is populated and start Uvicorn with `--env-file .env`.

### Authentication returns 503

Authentication needs PostgreSQL and applied migrations. Run the full pipeline
with `DATABASE_URL` configured.

### Chatbot returns 503

Set `ANTHROPIC_API_KEY` and restart the API. The chatbot is optional.

### Model training reports insufficient rows or one target class

Look at the source warnings and provenance. Restore network access or the
missing credentials, then rerun the build with `--refresh`.
