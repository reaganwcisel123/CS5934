#!/usr/bin/env bash
# Train the notifiable-disease forecast (US-050) and print its backtest.
# Refreshes the NNDSS history first so the forecast reflects the latest week.
set -euo pipefail

cd "$(dirname "$0")/.."

uv sync --frozen --extra model
uv run --frozen python -m src.ingestion.cdc_nndss
uv run --frozen python -m src.model.forecast --backtest --train
