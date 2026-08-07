# Explainer Chatbot: Design and Implementation

A chat assistant that explains the Clinic Needs Atlas data ("why is this county
high-need?"). The roadmap flagged this as its own track because the risk isn't
the plumbing, it's grounding: a health-data assistant that invents a number is
worse than no assistant. This doc records the design decision and where it now
lives in code: `src/api/chat.py` (backend) and
`dashboard/app/components/chat.js` (widget).

## Interaction model (HCI)
- Scope: answers about the currently selected county's data. The numbers on
  screen, what they mean, how they compare to the baseline. Not a general
  medical chatbot, not advice.
- Placement: a dockable panel launched from a button in the Signal dashboard.
  It carries the selected county as context, so "explain this" just works. The
  widget is route-aware and offers different starter questions per view
  (including the Funding Matches tab).
- Availability: only when a backend API is configured. The LLM call is
  server-side so the key never reaches the browser; in the static demo the
  widget isn't rendered at all.
- Tone: plainspoken, credible, concise. Matches the Triad voice. No emoji.

## Grounding strategy (the core decision)
Our data is small and structured (133 counties, a handful of metrics each,
plus a catalog), so we do retrieval over our own structured data rather than a
vector DB:
1. On each question, the backend assembles the selected county's record with
   provenance and a metric legend, and injects it as the grounding context
   (`_context()` in `src/api/chat.py`).
2. The system prompt constrains the model to answer only from that context,
   name the source for each figure (CDC PLACES, HRSA, and so on), flag
   pending/stub values as placeholders, and say "I don't have that data"
   rather than guess.
3. Every figure the model can cite traces to a `source_id` in the catalog, the
   same provenance the dashboard badges. No number exists in the answer that
   isn't in the context.

This makes hallucinated statistics structurally hard: the model is handed the
exact numbers and told to use only those.

## Guardrails (as built)
- No invented numbers; the model answers only from the injected data.
- Provenance-honest: pending/stub values are labelled as placeholders, never
  presented as measured.
- Scope limits: not medical advice, and it declines out-of-scope questions.
- Cost and abuse: the key stays server-side and `max_tokens` is capped (700).
  An in-process sliding-window rate limit applies per signed-in user, or per
  client IP otherwise (defaults: 20 questions per 60s, tunable via
  `ATLAS_CHAT_RATE_MAX` / `ATLAS_CHAT_RATE_WINDOW`). When a signed-in user
  asks a question and the DB is configured, a `usage_event` row records it.

## Model & cost
- Official `anthropic` Python SDK, single `messages.create` call per question.
  Plain Q&A, not agentic.
- Default model `claude-opus-4-8`; `ATLAS_CHAT_MODEL` overrides. Grounded
  explanations are short, so cost per answer stays low.
- Needs `ANTHROPIC_API_KEY`. Without it, `POST /api/chat` returns a clear 503
  and the UI hides the assistant.

## Shipped scope
- `POST /api/chat {question, county_fips}` returns a grounded answer, covered
  by `tests/test_chat_api.py`.
- A county-aware chat widget in the dashboard.
- Still one question shape ("explain this county"). Cross-county comparisons
  and trend questions are candidates for a later pass, after evaluating how
  the single-county version holds up.
