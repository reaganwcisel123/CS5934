"""User accounts and usage-event storage (app_user, usage_event)."""

from __future__ import annotations

import json

from sqlalchemy import text

from src.db.engine import get_engine


def create_user(email: str, password_hash: str, role: str = "viewer", org: str | None = None) -> dict:
    with get_engine().begin() as c:
        row = c.execute(text(
            "insert into app_user(email,password_hash,role,org) values(:e,:h,:r,:o) "
            "returning id,email,role"),
            {"e": email, "h": password_hash, "r": role, "o": org}).mappings().first()
    return dict(row)


def get_user_by_email(email: str) -> dict | None:
    with get_engine().connect() as c:
        row = c.execute(text(
            "select id,email,password_hash,role from app_user where email=:e"),
            {"e": email}).mappings().first()
    return dict(row) if row else None


def record_event(user_id, event_type: str, county_fips: str | None = None,
                 metadata: dict | None = None) -> None:
    with get_engine().begin() as c:
        c.execute(text(
            "insert into usage_event(user_id,event_type,county_fips,metadata) "
            "values(:u,:t,:c,cast(:m as jsonb))"),
            {"u": user_id, "t": event_type, "c": county_fips,
             "m": json.dumps(metadata) if metadata else None})
