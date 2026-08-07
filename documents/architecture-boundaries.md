# Architecture Boundaries and Layering Contract

The rules that keep features decoupled: which layer may import which, what each
layer's public interface is, and how the rules are enforced mechanically so a
violation fails CI instead of quietly rotting the codebase.

Enforcement is [import-linter](https://import-linter.readthedocs.io/). The config
lives in `pyproject.toml` under `[tool.importlinter]`. Run it with:

```bash
uv run lint-imports
```

## The rule in one sentence
Dependencies point one way (downward). A lower layer never imports a higher one,
and independent units (the data sources) never import each other.

## Current layers (Python, `src/`), enforced today

Top imports downward; the bottom is pure. This matches the `layers` contract in
`pyproject.toml`, top to bottom:

| Layer | Module(s) | Responsibility | May import |
|---|---|---|---|
| API | `src.api` | FastAPI routers: atlas, auth, chat, forecast. Nothing imports it back. | everything below |
| Entry / orchestration | `src.build_dataset` | Wire the pipeline, produce the JSON, seed/score into the DB | model, ingestion, db, transform, catalog |
| Model | `src.model` | Risk model training/scoring, NNDSS forecasting | ingestion, db, transform, catalog |
| Ingestion | `src.ingestion.*` | One unit per source: fetch and shape to `county_fips` rows | db, transform, catalog, and the shared `base` / `_census` helpers |
| Data access | `src.db` | Engine, migration runner, queries, writers. The only code that talks to Postgres. | transform, catalog |
| Transform | `src.transform.*` | Pure logic (normalize, blend, need index, geographic join) | nothing internal |
| Catalog | `src.catalog` | Load the data source catalog (source of truth) | nothing internal |

Contracts beyond the layer order:
- `transform` and `catalog` are pure leaves. Each has its own `forbidden`
  contract saying it imports nothing else in `src`, so a change there can't
  ripple outward.
- `model` may not import `build_dataset` or `api` (a separate `forbidden`
  contract). Modeling code can't reach into orchestration or serving.
- Ingestion sources are mutually independent. An `independence` contract keeps
  `cdc_places` from importing `hrsa_hpsa` and so on. Shared behavior lives in
  `base` / `_census`, imported down, never sideways. This is what guarantees
  that adding or breaking one source can't affect another.

One known gap: `src/grants/` (the Grants.gov recommender) is not yet listed in
any contract, so import-linter doesn't constrain it. It currently only imports
`src.catalog`; it should be added to the `layers` contract.

## Public interface of each layer (import these, not internals)
- catalog: `Catalog` (`.load()`, `.source(id)`, `.sources`, lineage accessors). Don't read the YAML directly anywhere else.
- ingestion: `BaseSource` / `RealSource` / `StubSource` plus `REGISTRY`. Consumers use the registry, never a concrete source class by name.
- transform: the pure functions (`normalize_burden`, `blend_domain`, `need_index`, the geographic join). No I/O, no globals.
- db: `engine`, `queries`, `writer`. Nothing above this layer opens its own connection.
- build_dataset: CLI entry only; nothing imports it.
- api: HTTP surface only; nothing imports it.

## The frontend / backend boundary (not a Python import)
The frontend talks to the backend only over HTTP, against the FastAPI routes
under `/api/*`. In static mode the dashboard reads the built JSON instead.
Either way there is no shared code import to police. Still missing: a contract
test on the API schema (OpenAPI), so a breaking change fails CI the same way
the catalog validator guards `data_sources.yml`.

## How to extend without creating fragility
- Add a data source: new module in `src/ingestion/`, subclass `RealSource` or
  `StubSource`, one line in `registry.py`, and add it to the independence
  contract. Nothing else changes.
- Add a metric or transform: new pure function in `src/transform/`. It imports
  nothing internal, so it can't break anything.
- Add a layer or package: create it, then add it to the `layers` contract in
  `pyproject.toml` in the same PR. The boundary and its enforcement land
  together.

## Enforcement checklist
- [x] `import-linter` layering + independence contracts (`pyproject.toml`), run via `uv run lint-imports`.
- [x] CI runs the contract and the catalog validator on every PR (`.github/workflows/ci.yml`). Make it a required status check in branch protection so a failure blocks merging.
- [ ] Add the test suite and type check to the CI job. Placeholders are already in the workflow, and tests exist under `tests/`.
- [ ] API schema contract test.
- [ ] Add `src.grants` to the layers contract.
