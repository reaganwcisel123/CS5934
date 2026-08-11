"""Durable Postgres snapshot storage for hosted Funding Matches refreshes."""

from __future__ import annotations

import json
from typing import Any

from src.db.engine import db_configured, get_engine


def load_last_known_good() -> dict[str, Any] | None:
    """Read the latest validated artifact when Postgres is configured."""
    if not db_configured():
        return None
    with get_engine().connect() as connection:
        value = connection.exec_driver_sql("select artifact from grant_funding_snapshot where snapshot_key = 'current'").scalar()
    if not value:
        return None
    return value if isinstance(value, dict) else json.loads(value)


def save_snapshot(artifact: dict[str, Any]) -> None:
    """Atomically promote a fully-built artifact; never overwrite it mid-run."""
    if not db_configured():
        return
    payload = json.dumps(artifact, allow_nan=False)
    with get_engine().begin() as connection:
        connection.exec_driver_sql(
            "insert into grant_funding_snapshot(snapshot_key, artifact, generated_at) values ('current', cast(%s as jsonb), now()) "
            "on conflict (snapshot_key) do update set artifact = excluded.artifact, generated_at = excluded.generated_at",
            (payload,),
        )
