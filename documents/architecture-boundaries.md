# Architecture Boundaries & Layering Contract

The rules that keep features decoupled: which layer may import which, what each
layer's public interface is, and how the rules are **mechanically enforced** (so
a violation fails CI instead of quietly rotting the codebase).

Enforced by [import-linter](https://import-linter.readthedocs.io/) — config lives
in `pyproject.toml` under `[tool.importlinter]`. Run it with:

```bash
uv run lint-imports
```

## The rule in one sentence
**Dependencies point one way (downward). A lower layer may never import a higher
one, and independent units (data sources, later: features) may never import each
other.**

## Current layers (Python, `src/`) — enforced today

Top imports downward; bottom is pure.

| Layer | Module(s) | Responsibility | May import | Must NOT import |
|---|---|---|---|---|
| **Entry / orchestration** | `src.build_dataset` | Wire the pipeline, produce output | ingestion, transform, catalog | — (nothing imports it back) |
| **Ingestion** | `src.ingestion.*` | One unit per source: fetch + shape to `county_fips` rows | catalog, transform, `base`, `_census` | build_dataset; **any sibling source** |
| **Transform** | `src.transform.*` | Pure business logic (normalize, blend) | *(nothing internal — pure leaf)* | catalog, ingestion, build_dataset |
| **Catalog** | `src.catalog` | Load the data source catalog (source of truth) | *(nothing internal — foundation)* | everything else in `src` |

Two invariants beyond the layer order:
- **`transform` and `catalog` are pure leaves** — they import nothing else in `src`. Pure logic is safe to change because a change can't ripple outward.
- **Ingestion sources are mutually independent** — `cdc_places` cannot import `hrsa_hpsa`, etc. Shared behavior lives in `base` / `_census` (imported *down*, never sideways). This is what guarantees "adding/breaking one source can't affect another."

## Public interface of each layer (import these, not internals)
- **catalog** → `Catalog` (`.load()`, `.source(id)`, `.lineage`). Don't read the YAML directly anywhere else.
- **ingestion** → `BaseSource`/`RealSource`/`StubSource` + `REGISTRY`. Consumers use the registry, never a concrete source class by name.
- **transform** → the pure functions (`normalize_burden`, `blend_domain`). No I/O, no globals.
- **build_dataset** → CLI entry only; nothing imports it.

## Target layers (Phase 1+) — add to the contract as they're built

Same downward rule, extended for the dynamic platform:

```
api            (HTTP routers/handlers)              ← nothing imports it
  → services   (aggregation, business use-cases)
  → data-access (repositories: the only code that talks to the DB)
  → db/models  (schema/ORM)
ingestion      → catalog, transform, data-access(write)
transform      (pure)                               ← imports nothing internal
catalog        (source of truth)                    ← imports nothing internal
```

New rules to add when these exist:
- **Only `data-access` may import `db/models`.** Services and API never touch the ORM/SQL directly — they go through repositories. This keeps a schema change from rippling into business logic or the API.
- **`api` may not be imported by anything** (top layer).
- **`transform` and `catalog` stay pure leaves** even as the app grows.

## The Frontend ↔ Backend boundary (not a Python import)
The frontend talks to the backend **only over HTTP against a versioned API
schema** — never a shared code import. That schema *is* the contract:
- Generate/validate it (e.g. OpenAPI) and add a **contract test** so a breaking
  change fails CI, mirroring how the catalog validator guards `data_sources.yml`.
- The frontend depends on the schema, not on backend internals; the backend can
  refactor freely as long as the schema holds.

## How to extend without creating fragility
- **Add a data source:** new module in `src/ingestion/`, subclass `RealSource`/`StubSource`, add one line to `registry.py`. Add it to the independence contract. Nothing else changes.
- **Add a metric/transform:** new pure function in `src/transform/`. It imports nothing internal, so it can't break anything.
- **Add a layer (api/services/data-access):** create the package, then add it to the `layers` contract in `pyproject.toml` in the same PR — the boundary and its enforcement land together.

## Enforcement checklist (Phase 1 harness)
- [x] `import-linter` layering + independence contracts (`pyproject.toml`), run via `uv run lint-imports`.
- [x] CI runs the contract + catalog validator on every PR (`.github/workflows/ci.yml`). Make it a **required status check** in GitHub branch protection so failing = un-mergeable.
- [ ] Add tests + type check to the CI job as they land (placeholders already in the workflow).
- [ ] API schema contract test once the backend exists.
- [ ] Repository-only DB access rule added to the contract once `data-access` exists.
