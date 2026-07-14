#!/usr/bin/env bash
# One-command reproducible pipeline (US-023). Mirrors the Render build.
#   ./scripts/run-pipeline.sh                     # dashboard JSON only
#   DATABASE_URL=... ./scripts/run-pipeline.sh    # also migrate + load Postgres
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -n "${DATABASE_URL:-}" ]; then
  # Full platform path: migrate, build + seed, train models, then score + load.
  echo "==> DATABASE_URL set: migrate + seed + train + score + load Postgres"
  uv sync --extra api --extra model
  uv run python -m src.db.migrate
  uv run python src/build_dataset.py --refresh --seed
  uv run python -m src.model.train --target both
  uv run python src/build_dataset.py --score --to-db
else
  # Dashboard-only path: no database needed.
  echo "==> no DATABASE_URL: building dashboard JSON only"
  uv sync
  uv run python src/build_dataset.py --refresh
fi

echo "==> done: dataset at dashboard/data/clinic_atlas.json"
