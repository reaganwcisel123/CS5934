#!/usr/bin/env bash
# One-command reproducible pipeline (US-023). Mirrors the Render build.
#   ./scripts/run-pipeline.sh                     # dashboard JSON only
#   DATABASE_URL=... ./scripts/run-pipeline.sh    # also migrate + load Postgres
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -n "${DATABASE_URL:-}" ]; then
  # Full platform path: install API deps, migrate, then build + load Postgres.
  echo "==> DATABASE_URL set: migrate + seed + load Postgres"
  uv sync --extra api
  uv run python -m src.db.migrate
  uv run python src/build_dataset.py --refresh --seed --to-db
else
  # Dashboard-only path: no database needed.
  echo "==> no DATABASE_URL: building dashboard JSON only"
  uv sync
  uv run python src/build_dataset.py --refresh
fi

echo "==> done: dataset at dashboard/data/clinic_atlas.json"
