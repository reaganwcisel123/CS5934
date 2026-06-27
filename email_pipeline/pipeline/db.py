"""SQLite source of truth: a contacts table plus an append-only events log."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager

# Allowed values for contacts.status (the per-contact state machine):
# not_contacted -> sent -> responded, with bounced / opted_out branches.
STATUSES = ("not_contacted", "sent", "responded", "bounced", "opted_out")

# Database schema: one row per contact, one row per logged event.
SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    category          TEXT,
    organization      TEXT NOT NULL,
    contact_name      TEXT,
    role_title        TEXT,
    email             TEXT,          -- email from the curated contact list
    phone             TEXT,
    city              TEXT,
    state             TEXT,
    zip               TEXT,
    source            TEXT,          -- record provenance
    enriched_email    TEXT,          -- optional manual override of `email`
    -- state machine --
    status            TEXT NOT NULL DEFAULT 'not_contacted',
    opted_out         INTEGER NOT NULL DEFAULT 0,
    bounced           INTEGER NOT NULL DEFAULT 0,
    sent_at           TEXT,
    responded_at      TEXT,
    followups_sent    INTEGER NOT NULL DEFAULT 0,
    last_contact_at   TEXT,
    notes             TEXT,
    UNIQUE(email)
);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id  INTEGER REFERENCES contacts(id),
    ts          TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    channel     TEXT,               -- email|warm_intro|phone|form|system
    detail      TEXT
);

CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);
CREATE INDEX IF NOT EXISTS idx_events_contact ON events(contact_id);
"""


# Open a connection with row access by name and foreign keys on.
def connect(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Create the tables if they do not already exist.
def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


# Context manager that opens, initializes, commits, and closes a connection.
@contextmanager
def session(path: str):
    conn = connect(path)
    init(conn)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# --- writes -----------------------------------------------------------------

# Insert a contact, or update its static fields if the email already exists.
def upsert_contact(conn: sqlite3.Connection, row: dict) -> None:
    # Keyed on email so re-running ingest is idempotent and keeps campaign state.
    cols = [
        "category", "organization", "contact_name", "role_title", "email",
        "phone", "city", "state", "zip", "source",
    ]
    # Build the insert with an on-conflict update of every column except the key.
    values = [row.get(c, "") for c in cols]
    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "email")
    conn.execute(
        f"INSERT INTO contacts ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(email) DO UPDATE SET {updates}",
        values,
    )


# Move a contact to a new status and set any extra timestamp/flag fields.
def set_status(conn, contact_id: int, status: str, ts: str, **fields) -> None:
    assert status in STATUSES, f"unknown status {status!r}"
    # Always update status and last_contact_at, plus any keyword fields passed.
    sets = ["status=?", "last_contact_at=?"]
    params: list = [status, ts]
    for key, val in fields.items():
        sets.append(f"{key}=?")
        params.append(val)
    params.append(contact_id)
    conn.execute(f"UPDATE contacts SET {', '.join(sets)} WHERE id=?", params)


# Append one row to the audit log.
def log_event(conn, contact_id, ts, event_type, channel="system", detail="") -> None:
    conn.execute(
        "INSERT INTO events (contact_id, ts, event_type, channel, detail) VALUES (?,?,?,?,?)",
        (contact_id, ts, event_type, channel, detail),
    )


# --- reads ------------------------------------------------------------------

# Return every contact ordered by id.
def all_contacts(conn) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM contacts ORDER BY id").fetchall()


# Return contacts that can be emailed now: not contacted, has email, not opted out / bounced.
def sendable(conn) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM contacts WHERE status='not_contacted' AND opted_out=0 "
        "AND bounced=0 AND COALESCE(enriched_email, email, '') != '' ORDER BY id"
    ).fetchall()


# Return a {status: count} map across all contacts.
def status_counts(conn) -> dict:
    rows = conn.execute("SELECT status, COUNT(*) n FROM contacts GROUP BY status").fetchall()
    return {r["status"]: r["n"] for r in rows}
