"""Stage 5: send scheduled follow-up nudges to contacts that have not responded."""

from __future__ import annotations

from datetime import datetime, timezone

from . import config, db, send


# Current UTC timestamp as an ISO string.
def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Days elapsed since an ISO timestamp, or None if it is missing or unparseable.
def _days_since(iso_ts: str | None) -> float | None:
    if not iso_ts:
        return None
    # Parse the stored timestamp, tolerating a missing timezone.
    try:
        then = datetime.fromisoformat(iso_ts)
    except ValueError:
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - then).total_seconds() / 86400


# True if this contact is due for its next follow-up right now.
def due(contact: db.sqlite3.Row, cfg: dict, today_days=_days_since) -> bool:
    # Only nudge contacts that were sent and have not since changed state.
    if contact["status"] != "sent":
        return False
    if contact["opted_out"] or contact["bounced"]:
        return False
    # Stop once the follow-up cap or the cadence schedule is exhausted.
    n = contact["followups_sent"]
    if n >= cfg["max_followups"]:
        return False
    offsets = cfg["followup_offsets_days"]
    if n >= len(offsets):
        return False
    # Due once enough days have passed since the last contact.
    elapsed = today_days(contact["last_contact_at"] or contact["sent_at"])
    return elapsed is not None and elapsed >= offsets[n]


# Send (or dry-run) a follow-up to every contact currently due for one.
def run(cfg: dict | None = None, dry_run: bool = True) -> dict:
    cfg = cfg or config.load()
    service = None
    if not dry_run:
        service = send._gmail_service(cfg)

    sent = 0
    with db.session(cfg["database"]) as conn:
        for c in db.all_contacts(conn):
            if not due(c, cfg):
                continue
            # Reuse the send template so the nudge carries the same prefilled link.
            to = (c["enriched_email"] or c["email"]).strip()
            subject, body = send.render_email(cfg, c)
            subject = "Following up: " + subject
            # Dry run just reports who would be nudged.
            if dry_run:
                print(f"[followup] DUE: {c['organization']} ({to}) "
                      f"follow-up #{c['followups_sent'] + 1}")
                continue
            # Send, bump the follow-up count, and log the event.
            try:
                send._send_via_gmail(service, cfg["sender_email"], to, subject, body)
                db.set_status(conn, c["id"], "sent", now(),
                              followups_sent=c["followups_sent"] + 1)
                db.log_event(conn, c["id"], now(), "followup", "email",
                             f"follow-up #{c['followups_sent'] + 1}")
                sent += 1
            except Exception as exc:  # noqa: BLE001
                db.log_event(conn, c["id"], now(), "error", "email", f"followup failed: {exc}")

    mode = "DRY RUN" if dry_run else f"{sent} follow-ups sent"
    print(f"[followup] {mode}")
    return {"sent": sent, "dry_run": dry_run}


if __name__ == "__main__":
    run(dry_run=True)
