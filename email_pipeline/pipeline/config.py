"""Configuration loader: built-in defaults overlaid with an optional config.yaml."""

from __future__ import annotations

import os
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Built-in defaults so the credential-free stages work before any config exists.
DEFAULTS = {
    # --- data ---
    # Curated contact list (verified emails + attributes). Committed so the
    # pipeline stays reproducible from a checked-in source.
    "source_csv": os.path.join(ROOT, "contacts.csv"),
    "database": os.path.join(ROOT, "data", "outreach.db"),
    "report_path": os.path.join(ROOT, "data", "status_report.md"),
    # --- survey ---
    # Google Form prefill base. The clinic id is injected at the entry.XXX
    # parameter so every response maps back to a contact row.
    "survey_base_url": "https://docs.google.com/forms/d/e/REPLACE_FORM_ID/viewform",
    "survey_clinic_id_entry": "entry.000000000",
    "survey_responses_sheet_id": "REPLACE_GOOGLE_SHEET_ID",
    "survey_clinic_id_column": "Clinic ID",
    # --- sending ---
    "sender_name": "Virginia Tech CS5934 Capstone Team",
    "sender_email": "REPLACE_SENDER@vt.edu",
    "sender_physical_address": "Virginia Tech, Blacksburg, VA 24061",  # CAN-SPAM
    "send_throttle_seconds": 8,
    "gmail_credentials": os.path.join(ROOT, "credentials", "gmail_oauth.json"),
    "gmail_token": os.path.join(ROOT, "credentials", "gmail_token.json"),
    # --- cadence / cutoff ---
    "followup_offsets_days": [3, 7],   # up to two follow-ups
    "max_followups": 2,
    "response_cutoff": "2026-06-24",   # FRS deadline
    "low_response_threshold": 0.15,    # below 15% response rate, escalate
    "escalation_recipients": [
        "jpfautz@theauthenticconsortium.com",
        "drmaryclisbee@gmail.com",
    ],
}


def load(path: str | None = None) -> dict:
    import yaml

    cfg = dict(DEFAULTS)
    path = path or os.path.join(ROOT, "config.yaml")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
        cfg.update({k: v for k, v in loaded.items() if v is not None})
    return cfg


def cutoff_date(cfg: dict) -> date:
    return date.fromisoformat(str(cfg["response_cutoff"]))
