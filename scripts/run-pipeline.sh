#!/usr/bin/env bash
# One-command reproducible pipeline (US-023). Mirrors the Render build.
#   ./scripts/run-pipeline.sh                     # dashboard JSON only
#   DATABASE_URL=... ./scripts/run-pipeline.sh    # migrate + train + load Postgres
set -euo pipefail

cd "$(dirname "$0")/.."

# Load local configuration so `cp .env.example .env` is sufficient for the
# documented one-command workflow. Render injects variables directly.
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if [[ -n "${DATABASE_URL:-}" ]]; then
  echo "==> DATABASE_URL set: migrate + seed + train + score + load Postgres"

  uv sync --frozen --extra api --extra model
  uv run --frozen python -m src.db.migrate
  uv run --frozen python src/build_dataset.py --refresh --seed
  uv run --frozen python -m src.model.train --target both
  uv run --frozen python src/build_dataset.py --score --to-db
else
  echo "==> no DATABASE_URL: building dashboard JSON only"

  uv sync --frozen
  uv run --frozen python src/build_dataset.py --refresh
fi

echo "==> done: dataset at dashboard/data/clinic_atlas.json"
