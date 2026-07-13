-- Scored synthetic patients (non-PHI) so the live API can serve the RiskPanel.
-- One row per (county, patient, vintage); risk fields come from src/model.
create table if not exists patient (
  id           bigint generated always as identity primary key,
  county_fips  text not null references county(fips) on delete cascade,
  patient_key  text not null,
  as_of        date not null default current_date,
  name         text,
  age          integer,
  risk         numeric,
  risk_tier    text,
  risk_drivers jsonb,
  attrs        jsonb,
  unique (county_fips, patient_key, as_of)
);
create index if not exists patient_county_idx on patient (county_fips, as_of);
