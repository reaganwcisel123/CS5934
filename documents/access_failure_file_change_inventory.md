# Rural Care Access Failure Model: File Change Inventory

## Purpose and Scope

This document inventories every tracked modification and every new source,
test, dashboard, and documentation file introduced for the Rural Care Access
Failure Model. The product objective is to give Virginia county planners a
clearly bounded, county-level signal for unusually high preventable hospital
stays associated with access barriers. It is a planning aid, not an individual
prediction, causal conclusion, or replacement for clinical judgment.

The work adds a separate **Access Failure Risk** tab to the canonical live
comparative dashboard. It does **not** modify
`dashboard/clinic-needs-forest.html`, the Virginia map with forest glyphs, nor
does it change the existing Comparative Atlas visualizations, selection flow,
or provenance strip.

## Modified Files

| File | Change | Product significance |
| --- | --- | --- |
| `README.md` | Documents the model purpose, County Health Rankings source, limitations, artifacts, and the train-then-build workflow. | Makes the feature reproducible and communicates appropriate use to future contributors. |
| `dashboard/clinic-needs-atlas-live.html` | Adds only tab navigation, two tab-panel containers, links to the dedicated assets, and an additive data handoff. | Provides a discoverable entry point while preserving the default Comparative Atlas experience. |
| `data_source_catalog/config/data_sources.yml` | Registers the official County Health Rankings & Roadmaps national analytic source, release details, fields, limitations, and adapter location. | Establishes data governance and makes the origin of the planning signal auditable. |
| `data_source_catalog/config/field_lineage.json` | Adds machine-readable lineage for raw source fields, the target, predictions, tiers, drivers, and release year. | Supports traceability tooling and downstream audit requirements. |
| `data_source_catalog/config/field_lineage.yml` | Adds the human-maintained YAML form of the same lineage records. | Keeps the catalog source of truth readable during review and maintenance. |
| `data_source_catalog/docs/data_source_catalog.md` | Describes the source's allowed use, local override, and Medicare-enrollee limitation. | Prevents the metric from being mistaken for a measure of every resident or causal access effect. |
| `pyproject.toml` | Adds the ingestion adapter to the import-linter independence contract. | Preserves architectural boundaries as the codebase gains a national model source. |
| `src/build_dataset.py` | Optionally joins valid FIPS-keyed predictions to county records and emits top-level model metadata. It deliberately excludes the risk field from the existing provenance payload. | Existing consumers remain compatible; only the new tab reads the additive model fields. |
| `src/ingestion/registry.py` | Registers the new source adapter without adding it to the normal Virginia dashboard-source spine. | Avoids making a national training source mandatory for existing dashboard builds. |
| `src/model/config.py` | Defines the model version, five allowed predictors, target threshold rule, display tiers, and driver labels. | Centralizes modeling policy and prevents undocumented feature drift. |
| `src/model/dataset.py` | Builds the national modeling frame, applies leakage checks, derives broadband gap, and records source metadata. | Produces a reproducible training dataset whose target is not accidentally used as a predictor. |
| `src/model/train.py` | Adds the access-failure training target, holdout/CV evaluation, artifact writing, FIPS prediction serialization, tiering, and explanation output. | Turns governed source data into reviewable model artifacts and county-level planning signals. |

## New Files

| File | What it does | Product significance |
| --- | --- | --- |
| `dashboard/access-failure-tab.js` | Owns all new-tab state, events, rendering, filtering, sorting, local county selection, detail panel, methodology, and source citation. | Keeps the feature isolated from the original dashboard's global state and interactions. |
| `dashboard/access-failure-tab.css` | Supplies responsive styles scoped exclusively to `access-failure-*` classes. | Prevents the risk tab from altering existing layout, controls, or visual styling. |
| `documents/access_failure_data_science_report.md` | Records the data frame, target construction, candidate models, metrics, limitations, and actual training results. | Gives reviewers enough evidence to assess fitness for a planning-support use case. |
| `documents/access_failure_implementation.md` | Explains architecture, data contract, operational workflow, testing, and preservation controls. | Helps maintainers safely operate and extend the feature. |
| `src/ingestion/county_health_rankings.py` | Downloads or reads the official CSV, normalizes county FIPS, removes aggregate rows, validates selected columns, and supports cached/local input. | Converts an external national release into a dependable, testable source layer. |
| `tests/fixtures/county_health_rankings.csv` | Provides a compact official-schema-shaped input fixture. | Enables deterministic parser tests without relying on network access. |
| `tests/test_county_health_rankings.py` | Tests parsing, suppressed values, FIPS normalization, aggregate removal, and deterministic deduplication. | Protects ingestion quality when the publisher format changes. |
| `tests/test_access_failure.py` | Tests training-frame rules, leakage guardrails, artifact/prediction attachment, invalid-score rejection, metadata, and CLI behavior. | Protects the model contract and the additive dashboard-data boundary. |
| `tests/test_access_failure_dashboard.py` | Compares original styles and core functions to `HEAD`, verifies risk content is absent from the existing panel, and tests module isolation. | Prevents future feature work from silently changing the pre-existing dashboard. |

## Product-Level Impact

The feature expands the product from descriptive county comparison into a
bounded decision-support workflow: planners can identify counties with higher
predicted access-related avoidable-utilization risk, inspect transparent
drivers and model performance, and distinguish unavailable predictions from
low risk. It keeps the claim narrow through explicit limitations, official
source citations, and model metadata.

The implementation is intentionally additive. Existing visualizations,
including the separate forest-glyph Virginia map, remain available without
model dependencies or behavior changes. This lowers regression risk while
allowing the product team to later decide whether the risk tab should also be
integrated into the forest-map experience.

## Generated, Untracked Artifacts

Training writes ignored artifacts under `models/access_failure/`, including the
serialized model, metrics, model card, and FIPS-keyed predictions. Rebuilding
the dashboard writes `dashboard/data/clinic_atlas.json`; it contains 133
records, 130 scored counties, optional `accessFailureRisk` record objects, and
optional `accessFailureModel` metadata. These generated outputs are not source
files for commit.
