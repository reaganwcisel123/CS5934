"""SQLAlchemy engine from DATABASE_URL (the Render Postgres connection string)."""

from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def db_configured() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


@lru_cache
def get_engine() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (the Render Postgres connection string).")
    # Force the psycopg (v3) driver.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url, pool_pre_ping=True)
