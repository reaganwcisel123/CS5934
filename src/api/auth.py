"""Auth + usage-tracking routes (FastAPI-native, JWT sessions)."""

from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from src.api import security
from src.db import users
from src.db.engine import db_configured

router = APIRouter(prefix="/api", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


def _require_db() -> None:
    if not db_configured():
        raise HTTPException(503, "auth requires a database (set DATABASE_URL)")


class Credentials(BaseModel):
    email: str
    password: str


class Event(BaseModel):
    event_type: str
    county_fips: str | None = None
    metadata: dict | None = None


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if creds is None:
        raise HTTPException(401, "not authenticated")
    try:
        return security.decode_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid or expired token")


@router.post("/auth/register")
def register(body: Credentials) -> dict:
    _require_db()
    if users.get_user_by_email(body.email):
        raise HTTPException(409, "email already registered")
    u = users.create_user(body.email, security.hash_password(body.password))
    return {"email": u["email"], "role": u["role"],
            "token": security.create_token(u["email"], u["role"])}


@router.post("/auth/login")
def login(body: Credentials) -> dict:
    _require_db()
    u = users.get_user_by_email(body.email)
    if not u or not security.verify_password(body.password, u["password_hash"]):
        raise HTTPException(401, "invalid credentials")
    return {"email": u["email"], "role": u["role"],
            "token": security.create_token(u["email"], u["role"])}


@router.get("/auth/me")
def me(user: dict = Depends(current_user)) -> dict:
    return {"email": user["sub"], "role": user.get("role")}


@router.post("/events")
def log_event(ev: Event, user: dict = Depends(current_user)) -> dict:
    _require_db()
    u = users.get_user_by_email(user["sub"])
    users.record_event(u["id"] if u else None, ev.event_type, ev.county_fips, ev.metadata)
    return {"ok": True}
