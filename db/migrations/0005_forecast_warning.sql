-- Notifiable-disease forecasts and the county warnings derived from them (US-052).
-- State-level forecast rows are the source of truth; county rows are allocated,
-- which is why allocation_method is not nullable on the county table.

create table if not exists condition_forecast (
  id             bigint generated always as identity primary key,
  as_of          date not null default current_date,
  condition      text not null,
  status         text not null,               -- ok | insufficient_history
  horizon_weeks  integer not null,
  point_estimate numeric,
  lower_bound    numeric,
  upper_bound    numeric,
  as_of_year     integer,
  as_of_week     integer,
  weeks_stale    integer,
  model_version  text,
  unique (condition, as_of, horizon_weeks)
);

create table if not exists county_condition_warning (
  id                bigint generated always as identity primary key,
  as_of             date not null default current_date,
  county_fips       text not null references county(fips) on delete cascade,
  condition         text not null,
  allocated_point   numeric,
  allocated_lower   numeric,
  allocated_upper   numeric,
  population_share  numeric,
  -- Never null: a county figure that cannot say how it was derived must not exist.
  allocation_method text not null,
  supplies          jsonb,
  unique (county_fips, condition, as_of)
);

create index if not exists county_warning_idx on county_condition_warning (county_fips, as_of);
