#!/usr/bin/env bash
# Train the baseline risk models (predictive-engine foundation).
#   ./scripts/train-model.sh            # county + patient, prints PR-AUC + calibration
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --extra model
uv run python -m src.model.train --target both
