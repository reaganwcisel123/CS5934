#!/usr/bin/env bash
# Build the static dashboard for deployment.
# Installs uv (which brings its own Python per pyproject requires-python),
# then runs the pipeline to generate dashboard/data/clinic_atlas.json.
#
# Sources that fail (e.g. no CENSUS_API_KEY, upstream outage) degrade to stubs,
# so the build still succeeds and publishes a working dashboard.
set -euo pipefail

curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

uv run python src/build_dataset.py

echo "Built dashboard/data/clinic_atlas.json"

# On Render, point the dashboard at the API and require sign-in (live + auth).
# Unset locally, so the committed no-op config.js is kept (static, no gate).
if [ -n "${ATLAS_API_HOST:-}" ]; then
  {
    echo "window.CLINIC_ATLAS_API=\"https://${ATLAS_API_HOST}/api\";"
    echo "window.CLINIC_ATLAS_AUTH=true;"
  } > dashboard/config.js
  echo "Wrote dashboard/config.js -> https://${ATLAS_API_HOST}/api (auth on)"
fi
