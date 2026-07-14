#!/usr/bin/env bash
# Train the baseline and advanced county and patient risk models.
# Prints PR-AUC, calibration, and rurality fairness results.
set -euo pipefail

cd "$(dirname "$0")/.."

uv sync --frozen --extra model
uv run --frozen python -m src.model.train --target both
