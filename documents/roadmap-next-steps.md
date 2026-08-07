# Clinic Needs Atlas: Next Steps Roadmap

Purpose: turn the original MVP (static dashboard + build-time ETL on Render) into a
dynamic, authenticated, continuously-updating product. Items are grouped into
phases ordered by dependency, not by the order they were first raised.

Status note (2026-08): most of this roadmap has shipped. Phases 0 through 4 are
done in their essentials; what's left is scheduled ingestion, the remaining stub
sources, and a handful of polish items called out below. Kept as a record of the
plan and what fell out of it.

## Guiding principles
1. Document before rebuilding, so every downstream decision is informed by the current architecture.
2. Platform before features. The dynamic backend and database had to exist before auth, live aggregation, or the chatbot could be built on them.
3. UX after the platform: rebuild the UI once, inside the chosen framework.
4. Keep what works. The data source catalog stays the single source of truth; the ingestion layer and graceful degradation carry forward.

## The original 7 items, mapped to phases
| Item | Phase | Status |
|---|---|---|
| Proper design docs (DD + ERD) | Phase 0 | done |
| Set up a real dynamic site | Phase 1 | done |
| Persistent DB for continuous pull/aggregate | Phase 1 | done (DB); scheduled pull still open |
| Revamp UI to product-owner design | Phase 2 | done |
| Make the dashboard more intuitive | Phase 2 | done |
| Login + user auth + tracking | Phase 3 | done |
| Interactive explainer chatbot | Phase 4 | done |

Dependency flow: `Phase 0 (docs) → Phase 1 (platform + DB) → Phase 2 (UX) → Phase 3 (auth) → Phase 4 (chatbot)`

---

## Architecture principles: designing against fragility

The overriding goal: adding or modifying one feature must not be able to silently
degrade another. This is a known failure mode of fast, AI-assisted development.
The pressure is to make a change work *right here*, which quietly reaches across
boundaries and creates "fix A, break B" fragility.

Core insight: decoupling is enforced by contracts and automated checks, not by
discipline. If a boundary *can* be crossed without something failing, it
eventually will be. So the architecture must make illegal coupling fail a test,
not just be discouraged.

Principles, each present in today's code:
1. Stable contracts at every seam. Layers talk through a defined shape, so changes behind it don't leak. The catalog entry; the `county_fips` DataFrame every source returns; the API routes the dashboard reads.
2. One source of truth, referenced not duplicated. Catalog for sources, the ERD-defined data model for the DB, one API contract. Drift between duplicated definitions is the top AI-development failure mode. Never copy a shape, import it.
3. Registry / plugin extensibility. Add a unit and register it; never edit the core. `BaseSource` + `registry.py` make a new source one class plus one line.
4. One-way dependency layering: `frontend → API → services → data-access → DB`, and `ingestion → catalog`. No back-edges, no reaching through a layer.
5. Pure, isolated business logic. Transforms (`normalize_burden`, need-index, aggregation) are pure, tested functions; I/O lives at the edges.
6. Config and provenance as data, not branching code. Adding a source must not add `if/else` in the frontend; it reads provenance from data.
7. Feature isolation. Auth and the chatbot are removable modules behind clear interfaces, not logic sprinkled through the core. (This held: `src/api/auth.py` and `src/api/chat.py` are routers the app can drop.)

Enforcement, all in place now:
- Import-boundary linting via `import-linter` contracts in `pyproject.toml`, so illegal cross-layer imports fail mechanically.
- A test suite covering the seams (`tests/`), including the DB writer, API routes, forecast pipeline, and grants pipeline.
- CI on every PR (`.github/workflows/ci.yml`) alongside the Render preview deploy.

When a phase introduces a new seam, define its contract and its test in the same PR. That rule stays.

---

## Phase 0: foundations (done)
Goal: know exactly what we have and where we're going before rebuilding.

- [x] Current-state architecture doc: [architecture-current-state.md](architecture-current-state.md).
- [x] Data Dictionary: [data-dictionary.md](data-dictionary.md).
- [x] ERD, the target data model for the FastAPI + Render Postgres platform: [erd.md](erd.md).
- [x] Module boundaries and dependency rules: [architecture-boundaries.md](architecture-boundaries.md), enforced by import-linter.
- [x] Product-owner design requirements: the Triad/Signal design system was supplied and applied in the Signal dashboard.

---

## Phase 1: platform, dynamic site + persistent database (done except scheduling)
Goal: replace "static HTML + build-time JSON" with a real app backed by a database.

- [x] Stack chosen and built: FastAPI (`src/api/`) reusing `src/`, with Render Postgres (`render.yaml`) and migrations in `db/migrations/` run by `src/db/migrate.py`.
- [x] Enforcement harness: tests, import-linter, CI (see above).
- [x] Persistent database on Render Postgres, tables from the ERD.
- [x] API layer: `/api/counties`, `/api/counties/{fips}`, `/api/sources`, plus `/api/forecast` and `/api/threats` for the early-warning feature.
- [x] Dashboard reads the API (`dashboard/app/api.js`), falling back to the static `clinic_atlas.json` when no API is configured, so the static deploy still works.
- [ ] Move ingestion from deploy-time to scheduled. Today the full ETL, NNDSS refresh, and model training run in the Render build command; a Render Cron Job or Background Worker per source `refresh_cadence` is still the plan.

---

## Phase 2: UX redesign (done)
Goal: implement the product owner's design and make the dashboard genuinely easy to read.

- [x] Signal design system implemented across the SPA in `dashboard/app/` (overview, county, explore, worklist, trends, methods, and funding-matches views).
- [x] Panels reworked with onboarding/empty states and provenance kept visible.
- [x] The original template pages are preserved in `dashboard/` as design references.
- [ ] Mobile/responsive pass remains light; worth a dedicated look if field use becomes real.

D3 stayed for the bespoke visuals; no charting library was adopted.

---

## Phase 3: auth and user tracking (done)
Goal: login, authenticated users, usage tracking.

- [x] FastAPI-native auth (`src/api/auth.py`, `src/api/security.py`): bcrypt password hashing, JWT sessions, no external provider.
- [x] `app_user` and `usage_event` tables (`db/migrations/0001_init.sql`), with a `role` column carried in the token.
- [x] Usage tracking: the dashboard posts fire-and-forget events to `/api/events` when signed in.
- [ ] Retention and privacy stance for usage events is still undocumented. Write it down before any real users exist.

---

## Phase 4: explainer chatbot (done)
Goal: a chat assistant that explains the data ("why is this county high-need?").

- [x] Grounded, not free-generating: `src/api/chat.py` makes a single Claude call over the selected county's atlas record, so answers trace to served data.
- [x] Guardrails: bearer-token auth path, per-user rate limiting, and the endpoint degrades to 503 without an `ANTHROPIC_API_KEY` rather than breaking the app.
- [ ] Expand beyond the single county-explainer question type; evaluate before widening scope.

---

## Shipped outside the original plan

- Early warning (US-048 through US-056): NNDSS ingestion with neighbouring states, per-condition forecasts with conformal intervals, threat ranking, supply guidance, allocation-fairness audit, and the Trends tab that serves it. See `forecast-model-card.md`.
- Grant funding recommender: Grants.gov ingestion and catalog integration (`src/grants/`), a rural-clinic matching pipeline, and an isolated Funding Matches dashboard tab reading `dashboard/data/grant_funding_matches.json`. The `grants_gov` entry that was a stub source now has a real pipeline; its stub class remains only as the catalog placeholder for the county-merge registry, which Grants.gov data doesn't join into.

## Cross-cutting / still open
- The 3 `USER CONTRIBUTION` seams (`normalize_burden`, need-index reweighting, stub contract) still run on defaults; the real strategies are still to be decided.
- 9 stub sources remain in `src/ingestion/stubs.py` (down from 11: `cdc_nndss` was promoted to a real source in US-048, and Grants.gov got its own pipeline). Wire them as scheduled ingestion makes continuous pull worthwhile.
- Optionally bump the wired sources' `ingestion_status` in the catalog to reflect they're live.

## Suggested next action
Scheduled ingestion is the one Phase 1 item left and the prerequisite for the
remaining stubs mattering. After that: the usage-event privacy note and a
responsive pass.
