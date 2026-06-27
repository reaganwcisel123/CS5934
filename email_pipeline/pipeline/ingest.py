"""Stage 1: load the curated contact list (CSV) into the source-of-truth database."""

from __future__ import annotations

import csv

from . import config, db

# Accepted CSV headers (case-insensitive) mapped to our column names.
# Only `organization` and `email` are required; the rest are optional.
COLUMN_MAP = {
    "organization": "organization",
    "email": "email",
    "contact_name": "contact_name",
    "role_title": "role_title",
    "phone": "phone",
    "city": "city",
    "state": "state",
    "zip": "zip",
    "category": "category",
    "source": "source",
}


# Read the CSV into a list of lowercase-keyed, stripped dict rows.
def _read_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = []
        for raw in reader:
            row = {}
            # Normalize each cell and ignore column-count drift.
            for key, val in raw.items():
                if key is None:
                    continue  # extra columns beyond the header (DictReader restkey)
                if isinstance(val, list):
                    val = val[0] if val else ""  # ragged row padding
                row[key.strip().lower()] = (val or "").strip()
            rows.append(row)
        return rows


# Upsert every valid row into the contacts table and report the counts.
def run(cfg: dict | None = None) -> dict:
    cfg = cfg or config.load()
    rows = _read_csv(cfg["source_csv"])

    inserted = skipped = 0
    with db.session(cfg["database"]) as conn:
        for row in rows:
            # Require organization and email; skip and count anything missing them.
            mapped = {dest: row.get(src, "") for src, dest in COLUMN_MAP.items()}
            if not mapped.get("organization") or not mapped.get("email"):
                skipped += 1
                continue
            mapped["email"] = mapped["email"].lower()
            db.upsert_contact(conn, mapped)
            inserted += 1

    summary = {"records": inserted, "skipped": skipped}
    print(f"[ingest] {inserted} clinics loaded from {cfg['source_csv']}")
    if skipped:
        print(f"[ingest] {skipped} row(s) skipped (missing organization or email).")
    return summary


if __name__ == "__main__":
    run()
