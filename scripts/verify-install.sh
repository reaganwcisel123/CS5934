#!/usr/bin/env bash
# Verify that a checkout can be installed, built, tested, and served.
#
# Usage:
#   ./scripts/verify-install.sh                   # dashboard + JSON API fallback
#   ./scripts/verify-install.sh --refresh         # force upstream downloads
#   ./scripts/verify-install.sh --full --refresh  # also train + score both models
#   ./scripts/verify-install.sh --with-db         # full path + PostgreSQL writes
set -euo pipefail

cd "$(dirname "$0")/.."

FULL=0
WITH_DB=0
REFRESH=0

usage() {
  cat <<'USAGE'
Usage: ./scripts/verify-install.sh [--refresh] [--full] [--with-db]

  --refresh   Ignore data/raw cache and fetch current upstream data.
  --full      Train both models and attach scores after the dataset build.
  --with-db   Apply migrations and load the configured PostgreSQL database.
              Requires DATABASE_URL and implies --full.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --refresh)
      REFRESH=1
      ;;
    --full)
      FULL=1
      ;;
    --with-db)
      WITH_DB=1
      FULL=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it from https://docs.astral.sh/uv/." >&2
  exit 1
fi

if [[ "$WITH_DB" -eq 1 && -z "${DATABASE_URL:-}" ]]; then
  echo "--with-db requires DATABASE_URL in the environment or .env." >&2
  exit 1
fi

run_uv() {
  uv run --frozen "$@"
}

echo "==> Installing locked API and model dependencies"
uv sync --frozen --extra api --extra model

echo "==> Validating the data-source catalog"
run_uv python data_source_catalog/scripts/validate_data_catalog.py

build_args=()
if [[ "$REFRESH" -eq 1 ]]; then
  build_args+=(--refresh)
fi

if [[ "$WITH_DB" -eq 1 ]]; then
  echo "==> Applying PostgreSQL migrations"
  run_uv python -m src.db.migrate

  echo "==> Building the dataset and seeding catalog metadata"
  run_uv python src/build_dataset.py "${build_args[@]}" --seed
else
  echo "==> Building the dashboard dataset"
  run_uv python src/build_dataset.py "${build_args[@]}"
fi

if [[ "$FULL" -eq 1 ]]; then
  echo "==> Checking model-training data"
  run_uv python - <<'PY'
from src.model.dataset import county_frame, patient_frame

county_x, county_y, _ = county_frame()
patient_x, patient_y, _, _ = patient_frame()

if len(county_x) < 2 or county_y.nunique() < 2:
    raise SystemExit(
        "County training data is unavailable or contains only one target class. "
        "Check source warnings and rerun with working network access and credentials."
    )
if len(patient_x) < 2 or patient_y.nunique() < 2:
    raise SystemExit("Synthetic patient training data is unavailable.")

print(f"county training rows: {len(county_x)}")
print(f"patient training rows: {len(patient_x)}")
PY

  echo "==> Training county and patient models"
  run_uv python -m src.model.train --target both

  if [[ "$WITH_DB" -eq 1 ]]; then
    echo "==> Scoring and loading PostgreSQL"
    run_uv python src/build_dataset.py --score --to-db
  else
    echo "==> Attaching model scores to the dashboard JSON"
    run_uv python src/build_dataset.py --score
  fi
fi

echo "==> Running tests"
run_uv pytest -q

echo "==> Checking architecture boundaries"
run_uv lint-imports

echo "==> Smoke-testing generated files and API routes"
ATLAS_VERIFY_WITH_DB="$WITH_DB" run_uv python - <<'PY'
import json
import os
from pathlib import Path

with_db = os.environ.get("ATLAS_VERIFY_WITH_DB") == "1"
if not with_db:
    # The default path intentionally verifies the JSON fallback even when a
    # developer has DATABASE_URL configured in the parent shell.
    os.environ.pop("DATABASE_URL", None)

atlas_path = Path("dashboard/data/clinic_atlas.json")
if not atlas_path.exists():
    raise SystemExit(f"Missing generated dataset: {atlas_path}")

atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
records = atlas.get("records") or []
if not records:
    raise SystemExit("Generated atlas contains no county records")

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)
responses = {
    "health": client.get("/api/health"),
    "counties": client.get("/api/counties"),
    "sources": client.get("/api/sources"),
}

for name, response in responses.items():
    if response.status_code != 200:
        raise SystemExit(
            f"API {name} smoke test failed: {response.status_code} {response.text}"
        )

health_body = responses["health"].json()
if bool(health_body.get("db")) != with_db:
    raise SystemExit(f"Unexpected database mode in health response: {health_body}")

county_body = responses["counties"].json()
api_count = county_body.get("county_count")
if with_db:
    if not isinstance(api_count, int) or api_count < 1:
        raise SystemExit(f"Database-backed API returned invalid count: {api_count}")
else:
    if api_count != len(records):
        raise SystemExit(
            "API county count does not match generated JSON: "
            f"api={api_count} json={len(records)}"
        )

first_fips = records[0]["id"]
county_response = client.get(f"/api/counties/{first_fips}")
if county_response.status_code != 200:
    raise SystemExit(f"County detail smoke test failed for {first_fips}")

print(f"API mode: {'PostgreSQL' if with_db else 'JSON fallback'}")
print(f"Verified county records: {len(records)}")
PY

echo "==> Installation verification passed."
