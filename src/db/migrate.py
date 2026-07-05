"""Apply SQL migrations in db/migrations/ to DATABASE_URL (idempotent).

Run:  uv run --env-file .env python -m src.db.migrate
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from src.db.engine import get_engine

MIG_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations"


def _statements(sql: str) -> Iterator[str]:
    # Drop line comments, split on ';' (our DDL has no embedded semicolons).
    body = "\n".join(ln for ln in sql.splitlines() if not ln.strip().startswith("--"))
    for stmt in body.split(";"):
        s = stmt.strip()
        if s:
            yield s


def apply() -> None:
    eng = get_engine()
    with eng.begin() as c:
        c.exec_driver_sql(
            "create table if not exists schema_migrations "
            "(name text primary key, applied_at timestamptz default now())")
        done = {r[0] for r in c.exec_driver_sql("select name from schema_migrations")}

    for f in sorted(MIG_DIR.glob("*.sql")):
        if f.name in done:
            print(f"skip {f.name} (already applied)")
            continue
        with eng.begin() as c:
            for stmt in _statements(f.read_text(encoding="utf-8")):
                c.exec_driver_sql(stmt)
            c.exec_driver_sql("insert into schema_migrations(name) values (%s)", (f.name,))
        print(f"applied {f.name}")


if __name__ == "__main__":
    apply()
