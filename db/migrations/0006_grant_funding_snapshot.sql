create table if not exists grant_funding_snapshot (
  snapshot_key text primary key,
  artifact jsonb not null,
  generated_at timestamptz not null default now()
);
