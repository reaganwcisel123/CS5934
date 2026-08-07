"""Grounded explainer chatbot (single Claude call over the selected county's data)."""

from __future__ import annotations

import os
import time
from collections import deque

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from src.api import security
from src.api.atlas import get_county, load_atlas
from src.db.engine import db_configured

router = APIRouter(prefix="/api", tags=["chat"])
_bearer = HTTPBearer(auto_error=False)
MODEL = os.environ.get("ATLAS_CHAT_MODEL", "claude-opus-4-8")

# In-process sliding-window rate limit (per user when signed in, else client IP).
# Single-instance only; move to a shared store if the API scales past one process.
RATE_MAX = int(os.environ.get("ATLAS_CHAT_RATE_MAX", "20"))
RATE_WINDOW = int(os.environ.get("ATLAS_CHAT_RATE_WINDOW", "60"))
_hits: dict[str, deque] = {}


def _enforce_rate(key: str) -> None:
    now = time.monotonic()
    # Evict other clients' fully-expired entries so the map can't grow forever.
    for k in [k for k, q in _hits.items() if k != key and q and now - q[-1] > RATE_WINDOW]:
        del _hits[k]
    dq = _hits.setdefault(key, deque())
    while dq and now - dq[0] > RATE_WINDOW:  # drop timestamps outside the window
        dq.popleft()
    if len(dq) >= RATE_MAX:
        raise HTTPException(429, f"rate limit: max {RATE_MAX} questions per {RATE_WINDOW}s")
    dq.append(now)

DOMAIN_META = {"economic": ("Economic", "Census ACS"), "education": ("Education", "Census ACS"),
               "food": ("Food/Housing", "USDA"), "environment": ("Environment", "CDC EJI"),
               "access": ("Care access", "HRSA HPSA")}
OUTCOME_META = {"diabetes": "Diabetes", "obesity": "Obesity",
                "mhlth": "Mental distress", "bphigh": "High BP"}

SYSTEM = (
    "You are the assistant for the Clinic Needs Atlas, a Virginia county health-needs "
    "dashboard (the Triad 'Signal' product). Explain the data to clinic administrators "
    "and analysts in plain, credible language.\n"
    "Rules:\n"
    "- Answer ONLY using the county data in the user's message. Do not use outside "
    "knowledge or invent numbers.\n"
    "- When you cite a figure, name its source (e.g. CDC PLACES, HRSA) and whether it "
    "is live or PENDING.\n"
    "- Values marked PENDING are placeholders for a source not yet wired; say so and "
    "never present them as measured.\n"
    "- The unmet-need index is a computed 0-100 composite; SDoH burdens are 0-100 "
    "(higher = more need); outcomes are % of adults.\n"
    "- If the question asks for something not in the data, say you don't have that data "
    "rather than guessing. You are not giving medical advice.\n"
    "- Be concise (a few sentences). No emoji. Sentence case."
)


class ChatRequest(BaseModel):
    question: str
    county_fips: str | None = None


def _optional_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict | None:
    if creds is None:
        return None
    try:
        return security.decode_token(creds.credentials)
    except Exception:
        return None


def _context(fips: str | None) -> str:
    prov = load_atlas().get("provenance") or {}
    status = lambda k: (prov.get(k) or {}).get("status")  # noqa: E731
    c = get_county(fips) if fips else None
    if not c:
        return "No county is currently selected."
    lines = [f"County: {c['name']} ({c.get('region')} region)",
             f"Unmet-need index: {c.get('needIndex')}/100 (computed composite)",
             f"Primary-care HPSA score: {c.get('hpsaScore')}/26 — source hrsa_hpsa ({status('hpsaScore') or 'n/a'})",
             "SDoH burden (0-100, higher = more need):"]
    for key, (label, src) in DOMAIN_META.items():
        st = status(f"dom.{key}")
        tag = "PENDING placeholder" if st == "stub" else (st or "n/a")
        lines.append(f"  - {label}: {c['dom'].get(key)} — {src} ({tag})")
    lines.append(f"Health outcomes (% of adults, CDC PLACES, {status('outcomes') or 'n/a'}):")
    for key, label in OUTCOME_META.items():
        v = c["outcomes"].get(key)
        lines.append(f"  - {label}: {v}%" if v is not None else f"  - {label}: not available")
    lines.append("Note: PENDING values are placeholders until that source is wired; do not treat them as measured.")
    return "\n".join(lines)


@router.post("/chat")
def chat(body: ChatRequest, request: Request, user: dict | None = Depends(_optional_user)) -> dict:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "chatbot not configured (set ANTHROPIC_API_KEY)")
    _enforce_rate(user["sub"] if user else (request.client.host if request.client else "anon"))
    context = _context(body.county_fips)
    try:
        resp = anthropic.Anthropic().messages.create(
            model=MODEL, max_tokens=700, system=SYSTEM,
            messages=[{"role": "user", "content": f"County data:\n{context}\n\nQuestion: {body.question}"}])
    except anthropic.APIError as e:
        raise HTTPException(502, f"chat model error: {getattr(e, 'message', str(e))}")
    answer = "".join(b.text for b in resp.content if b.type == "text").strip()

    if user and db_configured():  # bind usage to the signed-in user when possible
        try:
            from src.db import users
            u = users.get_user_by_email(user["sub"])
            users.record_event(u["id"] if u else None, "chat", body.county_fips, {"q": body.question[:200]})
        except Exception:
            pass
    return {"answer": answer, "county_fips": body.county_fips, "model": MODEL}
