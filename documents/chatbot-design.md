# Phase 4 — Explainer Chatbot: Design Spike

A chat assistant that explains the Clinic Needs Atlas data ("why is this county
high-need?"). The roadmap flags this as its own track because the risk isn't the
plumbing — it's **grounding**: a health-data assistant that invents a number is
worse than no assistant. This spike settles that before the prototype.

## Interaction model (HCI)
- **Scope:** answers about the *currently selected county's* data — the numbers on
  screen, what they mean, and how they compare to the baseline. Not a general
  medical chatbot, not advice.
- **Placement:** a dockable panel launched from a button in the Signal dashboard;
  it always carries the selected county as context, so "explain this" just works.
- **Availability:** only when a backend API is configured (the LLM call is
  server-side so the key never reaches the browser). In the static demo it's hidden.
- **Tone:** plainspoken, credible, concise — matches the Triad voice. No emoji.

## Grounding strategy (the core decision)
Our data is small and structured (133 counties × ~17 metrics + a catalog), so we
do **retrieval over our own structured data**, not a vector DB:
1. On each question, the backend pulls the selected county's record + provenance +
   a metric legend and injects it as the grounding context.
2. The system prompt constrains the model to answer **only** from that context,
   **cite the source** for each figure (CDC PLACES, HRSA, …), flag **pending/stub**
   values as placeholders, and say "I don't have that data" rather than guess.
3. Every figure the model can cite traces to a `source_id` in the catalog — the
   same provenance the dashboard badges. No number exists in the answer that isn't
   in the context.

This makes hallucinated statistics structurally hard: the model is given the exact
numbers and told to use only those.

## Guardrails
- **No invented numbers** — answer only from the injected data.
- **Provenance-honest** — pending/stub values are labelled as placeholders, never
  presented as measured.
- **Scope limits** — not medical advice; declines out-of-scope questions.
- **Cost/abuse** — server-side key; short `max_tokens`; optional auth binds usage
  to a user (`usage_event`), so a deployment can rate-limit or require login.

## Model & cost
- Official `anthropic` Python SDK, single `messages.create` call (Q&A, not agentic).
- Default model `claude-opus-4-8` (env `ATLAS_CHAT_MODEL` overrides). Grounded
  explanations are short; `max_tokens` is small, so cost per answer is low.
- Needs `ANTHROPIC_API_KEY`; without it the endpoint returns a clear 503 and the
  UI hides the assistant.

## Prototype scope (this phase)
- `POST /api/chat {question, county_fips}` → grounded answer (backend).
- A county-aware chat widget in the dashboard.
- One question type ("explain this county"), then evaluate before expanding to
  cross-county comparisons or trend questions.
