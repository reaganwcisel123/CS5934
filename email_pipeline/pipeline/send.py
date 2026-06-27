"""Stage 3: send the survey invitation with a per-contact prefilled Form link."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote_plus

from . import config, db


# Current UTC timestamp as an ISO string.
def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Build a Google Form prefill URL that carries the clinic id in a hidden field.
def prefilled_link(cfg: dict, contact_id: int) -> str:
    base = cfg["survey_base_url"]
    entry = cfg["survey_clinic_id_entry"]
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}usp=pp_url&{entry}={quote_plus(str(contact_id))}"


# Render the (subject, body) invitation for one contact.
def render_email(cfg: dict, contact: db.sqlite3.Row) -> tuple[str, str]:
    # Build the per-contact survey link and subject.
    org = contact["organization"].title()
    link = prefilled_link(cfg, contact["id"])
    subject = "5-minute survey: preventable hospitalizations in rural VA clinics"
    # Warm, CAN-SPAM-compliant body (physical address + one-click opt-out).
    body = f"""Hello {org} team,

We are a Virginia Tech capstone team working with the Authentic Consortium to
help rural Virginia clinics reduce preventable hospitalizations. We are gathering
brief, clinic-side input (no patient data) on the risk drivers and interventions
that matter most for clinics like yours.

Would someone on your team have 10-15 minutes to complete this short survey?

  {link}

Your response directly shapes a decision-support tool designed for small,
rural clinics. Responses are used in aggregate for an academic project.

Thank you,
{cfg['sender_name']}
{cfg['sender_email']}
{cfg['sender_physical_address']}

To opt out of further messages, reply with "unsubscribe".
"""
    return subject, body


# Authorize and return a Gmail API service. See README for one-time setup.
def _gmail_service(cfg: dict):  # pragma: no cover - needs credentials
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    import os

    # Load a cached token if present.
    scopes = ["https://www.googleapis.com/auth/gmail.send"]
    creds = None
    if os.path.exists(cfg["gmail_token"]):
        creds = Credentials.from_authorized_user_file(cfg["gmail_token"], scopes)
    # Otherwise refresh it or run the OAuth flow, then cache the result.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cfg["gmail_credentials"], scopes)
            creds = flow.run_local_server(port=0)
        with open(cfg["gmail_token"], "w") as fh:
            fh.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


# Send one message through the Gmail API.
def _send_via_gmail(service, sender: str, to: str, subject: str, body: str):  # pragma: no cover
    import base64
    from email.mime.text import MIMEText

    msg = MIMEText(body)
    msg["to"], msg["from"], msg["subject"] = to, sender, subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return service.users().messages().send(userId="me", body={"raw": raw}).execute()


# Send (or dry-run) the invitation to every sendable contact.
def run(cfg: dict | None = None, dry_run: bool = True, limit: int | None = None) -> dict:
    cfg = cfg or config.load()
    import time

    # Only build a Gmail service when actually sending.
    service = None
    if not dry_run:
        service = _gmail_service(cfg)

    sent = 0
    with db.session(cfg["database"]) as conn:
        # Pull the sendable contacts, optionally capped for a test run.
        targets = db.sendable(conn)
        if limit:
            targets = targets[:limit]
        for c in targets:
            to = (c["enriched_email"] or c["email"]).strip()
            subject, body = render_email(cfg, c)
            # Dry run just prints what would be sent.
            if dry_run:
                print(f"\n--- [DRY RUN] to {to} ({c['organization']}) ---")
                print(subject)
                print(body)
                continue
            # Send, advance the contact to sent, and throttle between messages.
            try:
                _send_via_gmail(service, cfg["sender_email"], to, subject, body)
                db.set_status(conn, c["id"], "sent", now(), sent_at=now())
                db.log_event(conn, c["id"], now(), "sent", "email", to)
                sent += 1
                time.sleep(cfg["send_throttle_seconds"])
            except Exception as exc:  # noqa: BLE001
                db.log_event(conn, c["id"], now(), "error", "email", f"send failed: {exc}")

    mode = "DRY RUN - nothing sent" if dry_run else f"{sent} invitations sent"
    print(f"\n[send] {mode}")
    return {"sent": sent, "dry_run": dry_run}


if __name__ == "__main__":
    run(dry_run=True)
