-- County-level model explainability (US-020): the top SDoH factors that push a
-- county into the high preventable-need tier. A short JSON array of labels,
-- computed in src/model/score.py from the linear model's per-feature contributions.
alter table county add column if not exists model_risk_drivers jsonb;
