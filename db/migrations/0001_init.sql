-- Clinic Needs Atlas - initial schema (see documents/erd.md).
-- Plain PostgreSQL for Render Postgres. The DB is reached only through the
-- FastAPI backend via DATABASE_URL, so no row-level security / public data API.
-- Apply with:  uv run --env-file .env python -m src.db.migrate

create table if not exists data_source (
  source_id          text primary key,
  name               text,
  provider           text,
  access_url         text,
  refresh_cadence    text,
  schema_version     text,
  ingestion_status   text,
  last_verified_date date
);

create table if not exists field_lineage (
  final_field       text primary key,
  source_id         text references data_source(source_id),
  original_field    text,
  transformation    text,
  required_for_mvp  boolean default false
);

create table if not exists county (
  fips        text primary key,
  name        text not null,
  region      text,
  district    text,
  rural       numeric,
  population  integer,
  updated_at  timestamptz default now()
);

-- Tall metrics table: one row per (county, metric, vintage) with provenance.
create table if not exists county_metric (
  id           bigint generated always as identity primary key,
  county_fips  text not null references county(fips) on delete cascade,
  metric_key   text not null,
  value        numeric,
  status       text not null default 'stub',
  source_id    text references data_source(source_id),
  as_of        date not null default current_date,
  unique (county_fips, metric_key, as_of)
);
create index if not exists county_metric_key_idx on county_metric (metric_key);

create table if not exists ingestion_run (
  id            bigint generated always as identity primary key,
  source_id     text references data_source(source_id),
  started_at    timestamptz default now(),
  finished_at   timestamptz,
  status        text,
  rows_written  integer,
  error         text
);

-- Users (Phase 3): app-managed accounts (auth handled in FastAPI, no external provider).
create table if not exists app_user (
  id            uuid primary key default gen_random_uuid(),
  email         text unique not null,
  password_hash text not null,
  role          text default 'viewer',
  org           text,
  created_at    timestamptz default now()
);

create table if not exists usage_event (
  id           bigint generated always as identity primary key,
  user_id      uuid references app_user(id) on delete set null,
  event_type   text not null,
  county_fips  text references county(fips),
  metadata     jsonb,
  ts           timestamptz default now()
);
