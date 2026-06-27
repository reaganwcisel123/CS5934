"""Stage 4a: ingest Google Form responses and mark contacts as responded."""

from __future__ import annotations

from datetime import datetime, timezone

from . import config, db


# Current UTC timestamp as an ISO string.
def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Open the linked responses sheet via gspread (needs Google credentials).
def _open_sheet(cfg: dict):  # pragma: no cover - needs credentials
    import gspread

    gc = gspread.oauth(
        credentials_filename=cfg["gmail_credentials"],
        authorized_user_filename=cfg["gmail_token"],
    )
    return gc.open_by_key(cfg["survey_responses_sheet_id"]).sheet1


# Return the responses sheet as a list of row dicts (isolated for testing).
def fetch_responses(cfg: dict) -> list[dict]:
    sheet = _open_sheet(cfg)
    return sheet.get_all_records()


# Match each response to a contact by the hidden Clinic ID and advance it.
def run(cfg: dict | None = None, responses: list[dict] | None = None) -> dict:
    cfg = cfg or config.load()
    id_col = cfg["survey_clinic_id_column"]
    rows = responses if responses is not None else fetch_responses(cfg)

    matched = unmatched = 0
    with db.session(cfg["database"]) as conn:
        for r in rows:
            # The Clinic ID is the contact's row id; skip anything non-numeric.
            raw_id = str(r.get(id_col, "")).strip()
            if not raw_id.isdigit():
                unmatched += 1
                continue
            # Look up the contact that this response belongs to.
            contact = conn.execute(
                "SELECT id, status FROM contacts WHERE id=?", (int(raw_id),)
            ).fetchone()
            if not contact:
                unmatched += 1
                continue
            # Advance to responded once (don't overwrite an existing response).
            if contact["status"] != "responded":
                db.set_status(conn, contact["id"], "responded", now(), responded_at=now())
                db.log_event(conn, contact["id"], now(), "responded", "form", "survey completed")
            matched += 1

    print(f"[track] {matched} responses matched, {unmatched} unmatched")
    return {"matched": matched, "unmatched": unmatched}


if __name__ == "__main__":
    run()
