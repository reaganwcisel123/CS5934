# Data Model (ERD)

The Postgres schema behind the live mode (FastAPI + Render Postgres).
Implemented in `db/migrations/0001_init.sql` and applied with
`uv run python -m src.db.migrate`. Ingestion writes here; FastAPI reads from it
and handles auth.

```mermaid
erDiagram
  COUNTY ||--o{ COUNTY_METRIC : has
  DATA_SOURCE ||--o{ COUNTY_METRIC : provides
  DATA_SOURCE ||--o{ FIELD_LINEAGE : maps
  DATA_SOURCE ||--o{ INGESTION_RUN : logs
  APP_USER ||--o{ USAGE_EVENT : generates
  COUNTY ||--o{ USAGE_EVENT : "viewed in"

  COUNTY {
    string fips PK
    string name
    string region
    string district
    float rural
    int population
    jsonb model_risk_drivers
    timestamptz updated_at
  }
  DATA_SOURCE {
    string source_id PK
    string name
    string provider
    string access_url
    string refresh_cadence
    string schema_version
    string ingestion_status
    date last_verified_date
  }
  FIELD_LINEAGE {
    string final_field PK
    string source_id FK
    string original_field
    string transformation
    bool required_for_mvp
  }
  COUNTY_METRIC {
    bigint id PK
    string county_fips FK
    string metric_key
    numeric value
    string status
    string source_id FK
    date as_of
  }
  INGESTION_RUN {
    bigint id PK
    string source_id FK
    timestamptz started_at
    timestamptz finished_at
    string status
    int rows_written
    text error
  }
  APP_USER {
    uuid id PK
    string email
    string password_hash
    string role
    string org
    timestamptz created_at
  }
  USAGE_EVENT {
    bigint id PK
    uuid user_id FK
    string event_type
    string county_fips FK
    jsonb metadata
    timestamptz ts
  }
```

Later migrations add tables not shown above:
- `patient` (0003): scored synthetic patients per county and vintage, so the
  live API can serve the risk panel. Unique on `(county_fips, patient_key, as_of)`.
- `county.model_risk_drivers` (0004): the top SDoH factors pushing a county
  into the high tier, computed in `src/model/score.py`.
- `condition_forecast` and `county_condition_warning` (0005): state-level
  NNDSS forecasts and the county warnings allocated from them.
  `allocation_method` is NOT NULL on the county table by design; an allocated
  figure that can't say how it was derived must not exist.

## Design choices (and why)
- `COUNTY_METRIC` is a tall table keyed by `metric_key` (e.g. `dom.economic`,
  `outcomes.diabetes`, `hpsa_score`) rather than one wide column per metric.
  Adding a new source or metric is an INSERT, not a schema migration, so new
  data can't break existing columns. Unique on `(county_fips, metric_key, as_of)`.
- Provenance lives on each value (`status`, `source_id`). The API can badge
  real/synthetic/stub exactly as the JSON does, and every value traces to a
  catalog source.
- The catalog is mirrored into the DB (`DATA_SOURCE`, `FIELD_LINEAGE`) so the
  API and future admin views read it from one place. `data_sources.yml` stays
  the authoring source of truth and seeds these tables
  (`build_dataset.py --seed`).
- `INGESTION_RUN` records each pull (source, timing, rows, errors):
  observability for the "constantly pull and aggregate" requirement.
- Auth is app-managed accounts in `APP_USER`. FastAPI handles login and JWT
  sessions (`src/api/auth.py`, `src/api/security.py`); no external provider.
  The DB is reached only through FastAPI, so access control lives in the API,
  not in the database. `USAGE_EVENT` captures tracking (county views, chat
  questions) with a `user_id` FK.

## How data gets in
`src/ingestion/*` returns `county_fips`-keyed frames. `src/db/writer.py`
upserts them into `COUNTY` + `COUNTY_METRIC` with provenance and records an
`INGESTION_RUN`; `src/db/forecast_writer.py` does the same for forecasts. On
Render this runs in the API service's build step (`render.yaml`), so data
refreshes on deploy rather than on a cron schedule for now. FastAPI exposes
the read endpoints (`/api/counties`, `/api/counties/{fips}`, `/api/sources`)
that the dashboard consumes in live mode instead of the static JSON.
