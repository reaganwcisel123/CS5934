# Clinic Needs Atlas — Next Steps Roadmap

Purpose: turn the current MVP (static dashboard + build-time ETL on Render) into a
dynamic, authenticated, continuously-updating product. Items are grouped into
phases ordered by dependency, not by the order they were first raised.

## Guiding principles
1. **Document before rebuilding** — capture the current architecture first so every downstream decision is informed.
2. **Platform before features** — the dynamic backend + database must exist before auth, live aggregation, or the chatbot can be built on them.
3. **UX after the platform** — rebuild the UI once, inside the chosen framework, to avoid throwing away work.
4. **Keep what works** — the data source catalog stays the single source of truth; the ingestion layer and graceful degradation carry forward.

## Your 7 items → phases at a glance
| Your item | Phase |
|---|---|
| Proper design docs (DD + ERD) | Phase 0 |
| Set up a real dynamic site | Phase 1 |
| Persistent DB for continuous pull/aggregate | Phase 1 |
| Revamp UI to product-owner design | Phase 2 |
| Make the dashboard more intuitive | Phase 2 |
| Login + user auth + tracking | Phase 3 |
| Interactive explainer chatbot | Phase 4 |

Dependency flow: `Phase 0 (docs) → Phase 1 (platform + DB) → Phase 2 (UX) → Phase 3 (auth) → Phase 4 (chatbot)`

---

## Architecture principles: designing against fragility

The overriding goal: **adding or modifying one feature must not be able to silently degrade another.** This is a known failure mode of fast / AI-assisted development — the pressure is to make a change work *right here*, which quietly reaches across boundaries and creates "fix A, break B" fragility.

Core insight: **decoupling is enforced by contracts and automated checks, not by discipline.** If a boundary *can* be crossed without something failing, it eventually will be. So the architecture must make illegal coupling fail a test, not just be discouraged.

**Principles** (each already partly present in today's code):
1. **Stable contracts at every seam.** Layers talk through a defined shape, so changes behind it don't leak. Today: the catalog entry; the `county_fips` DataFrame every source returns. Next: a versioned API schema between backend and frontend.
2. **One source of truth, referenced not duplicated.** Catalog for sources; one ERD-defined data model for the DB; one API contract. *Drift between duplicated definitions is the #1 AI-development failure mode* — never copy a shape, import it.
3. **Registry / plugin extensibility.** Add a unit and register it; never edit the core. Today: `BaseSource` + `registry.py` (a new source is one class + one line). Extend the same pattern to metrics and dashboard panels.
4. **One-way dependency layering.** Dependencies point one direction: `frontend → API → services → data-access → DB`, and `ingestion → catalog`. No back-edges, no reaching through a layer.
5. **Pure, isolated business logic.** Transforms (`normalize_burden`, need-index, aggregation) are pure, tested functions; I/O lives only at the edges. Pure logic is safe to change because it's testable in isolation.
6. **Config/provenance as data, not branching code.** Adding a source must not add `if/else` in the frontend — it reads provenance from data (as it does today).
7. **Feature isolation.** Auth and the chatbot are removable modules behind clear interfaces / feature flags, not logic sprinkled through the core.

**Enforcement — what makes it actually hold (build this in Phase 1):**
- **Boundary/contract tests** at each seam (extend the existing catalog validator pattern to the API schema — a breaking change fails CI, not prod).
- **Regression / characterization tests** so a change that degrades another feature is caught automatically.
- **Import-boundary linting** (e.g. `import-linter`) to forbid illegal cross-layer imports mechanically.
- **Type checking + small modules**, each with a defined public interface.
- **CI runs all of the above on every PR**, alongside the Render preview deploy.

> Every phase below should add a guardrail, not just a feature. When a phase introduces a new seam, define its contract and its test in the same PR.

---

## Phase 0 — Foundations: design docs & direction
**Goal:** know exactly what we have and where we're going before rebuilding.
**Depends on:** nothing. Start now; low risk, unblocks all decisions.
**Effort:** M

- [x] **Current-state architecture doc** — [architecture-current-state.md](architecture-current-state.md).
- [x] **Data Dictionary (DD)** — [data-dictionary.md](data-dictionary.md).
- [x] **ERD** — target data model for the FastAPI + Render Postgres platform: [erd.md](erd.md).
- [x] **Define module boundaries & dependency rules** — [architecture-boundaries.md](architecture-boundaries.md) (enforced by import-linter).
- [x] **Collect product-owner design requirements** — the Triad/Signal design system was supplied; applied in the Signal dashboard.

**Phase 0 complete.** Docs live in `documents/`, diagrams as in-repo Mermaid.

---

## Phase 1 — Platform: dynamic site + persistent database
**Goal:** replace "static HTML + build-time JSON" with a real app backed by a database that ingests on a schedule.
**Depends on:** Phase 0 ERD + stack decision.
**Effort:** L (the biggest architectural shift)

- [ ] **Choose the stack** (see open decision below).
- [ ] **Set up the anti-fragility enforcement harness first** — test framework, import-boundary linter, type checking, and CI on every PR (+ Render preview). Standing this up *before* feature work means every later boundary is guarded from day one.
- [ ] **Stand up a persistent database** (Render PostgreSQL). Design tables from the ERD.
- [ ] **Move ingestion from build-time → scheduled.** Reuse `src/ingestion/*` but write to Postgres instead of JSON, run on a Render Cron Job / Background Worker per each source's `refresh_cadence`.
- [ ] **Add an API layer** the frontend reads from (e.g. `/api/counties`), replacing the static `clinic_atlas.json` fetch.
- [ ] **Point the dashboard at the API** instead of the JSON file.

**Why this unlocks everything:** auth (Phase 3), user tracking, and the chatbot (Phase 4) all need a backend + DB. "Constantly pull and aggregate" is exactly the scheduled-ingestion-into-DB pattern.

**Decisions (locked):** **FastAPI** reusing `src/` for the backend + **Render
Postgres** for the database (everything under one roof on Render). Ingestion
writes to Postgres; FastAPI serves reads to the dashboard. Auth (Phase 3) is
handled in FastAPI, not an external provider. Target schema in [erd.md](erd.md).

---

## Phase 2 — UX: redesign & intuitiveness
**Goal:** implement the product owner's design and make the dashboard genuinely easy to read.
**Depends on:** Phase 0 (PO design requirements) + Phase 1 (build it in the real framework once).
**Effort:** M–L

- [ ] **Implement the PO design system** — colors, type, layout, components.
- [ ] **Rework the six panels** for clarity: better onboarding/empty states, clearer "what am I looking at" affordances, keep the provenance badges.
- [ ] **Intuitiveness pass** — guided first-run, tooltips, sensible default county, mobile/responsive.
- [ ] **Preserve the frozen template** (`clinic-needs-atlas.html`) as the design reference.

**Open decision:** keep D3 for the bespoke visuals vs. adopt a charting lib for the simpler panels.

---

## Phase 3 — Auth & user tracking
**Goal:** login page, authenticated users, and usage tracking.
**Depends on:** Phase 1 (backend + DB to store users/sessions/events).
**Effort:** M

- [ ] **Login page + FastAPI auth** — `APP_USER` table, password hashing, JWT sessions (no external provider).
- [ ] **User profile + sessions** in the DB (`APP_USER`, from the ERD); FastAPI issues/verifies the JWT.
- [ ] **Usage tracking** (`USAGE_EVENT`) — log page views, county selections, exports; document retention + privacy stance.
- [ ] **Role/permission model** enforced in FastAPI (the `role` column) if different users see different things.

**Open decision:** what "tracking" must capture (analytics vs. audit) and its privacy policy.

---

## Phase 4 — Interactive explainer chatbot (own track)
**Goal:** a chat assistant that explains the data ("why is this county high-need?").
**Depends on:** Phase 1 data layer + a dedicated design spike. Largest, most uncertain — keep separate.
**Effort:** XL

- [ ] **HCI / interaction design spike first** — where it lives, what it can/can't answer, how it cites the catalog, guardrails against hallucinated numbers.
- [ ] **Grounding strategy** — answer from the DB + catalog/field-lineage (retrieval over our own data), not free generation, so every claim traces to a source.
- [ ] **Prototype** on one question type, evaluate, then expand.
- [ ] **Model choice + cost/latency** budget.

**Open decision:** treat as a research spike before committing; it may reshape the UI (Phase 2), so at minimum align on placement early.

---

## Cross-cutting / carried forward
- The **3 `USER CONTRIBUTION` seams** (`normalize_burden`, need-index reweighting, stub contract) still run on defaults — decide the real strategies during Phase 1/2.
- **Wire the remaining 11 stub sources** (`src/ingestion/stubs.py`) as the DB makes continuous ingestion worthwhile.
- Optionally bump the 6 wired sources' `ingestion_status` in the catalog to reflect they're live.

## Suggested immediate next action
Start **Phase 0**: write the current-state architecture doc + ERD, and get the product owner's design requirements in hand — those two unblock the Phase 1 stack decision and the Phase 2 redesign in parallel.
