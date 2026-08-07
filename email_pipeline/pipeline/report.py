"""Stage 6: write the central status report and a low-response escalation memo."""

from __future__ import annotations

import os
from datetime import date, datetime, timezone

from . import config, db


def _coverage(conn) -> dict:
    row = conn.execute(
        "SELECT "
        "COUNT(*) total, "
        "SUM(CASE WHEN COALESCE(enriched_email,email,'')!='' THEN 1 ELSE 0 END) emailable "
        "FROM contacts"
    ).fetchone()
    return {"total": row["total"], "emailable": row["emailable"] or 0}


def build_report(cfg: dict) -> dict:
    # Read status counts and email coverage from the database.
    today = date.today()
    cutoff = config.cutoff_date(cfg)
    with db.session(cfg["database"]) as conn:
        counts = db.status_counts(conn)
        cov = _coverage(conn)

    sent = counts.get("sent", 0) + counts.get("responded", 0)
    responded = counts.get("responded", 0)
    rate = responded / sent if sent else 0.0
    # Escalate only past the cutoff and below the configured threshold.
    escalate = (today >= cutoff) and (rate < cfg["low_response_threshold"])

    return {
        "today": today,
        "cutoff": cutoff,
        "counts": counts,
        "coverage": cov,
        "total": cov["total"],
        "sent": sent,
        "responded": responded,
        "response_rate": rate,
        "escalate": escalate,
        "after_cutoff": today >= cutoff,
    }


def render_markdown(cfg: dict, r: dict) -> str:
    # Headline metrics.
    lines = [
        "# Survey Outreach Status Report (US-003)",
        "",
        f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}_",
        "",
        f"- Contacts total: **{r['total']}**",
        f"- With an email (emailable): **{r['coverage']['emailable']}**",
        f"- Invitations sent: **{r['sent']}**",
        f"- Responses: **{r['responded']}**",
        f"- Response rate: **{r['response_rate'] * 100:.1f}%** "
        f"(threshold {cfg['low_response_threshold'] * 100:.0f}%)",
        f"- Response cutoff: **{r['cutoff']}** "
        f"({'passed' if r['after_cutoff'] else 'open'})",
        "",
        "## Status breakdown",
        "",
        "| Status | Count |",
        "| --- | --- |",
    ]
    # One row per status in the state machine.
    for status in db.STATUSES:
        lines.append(f"| {status} | {r['counts'].get(status, 0)} |")
    lines.append("")
    # Append the escalation block when triggered.
    if r["escalate"]:
        lines += [
            "## ESCALATION REQUIRED",
            "",
            f"Response rate {r['response_rate'] * 100:.1f}% is below the "
            f"{cfg['low_response_threshold'] * 100:.0f}% threshold at the cutoff "
            f"({r['cutoff']}). Escalate to: " + ", ".join(cfg["escalation_recipients"]) + ".",
            "",
            "See `escalation_memo.md`.",
        ]
    return "\n".join(lines) + "\n"


def render_escalation_memo(cfg: dict, r: dict) -> str:
    return (
        "# Escalation: low survey response volume (US-003)\n\n"
        f"To: {', '.join(cfg['escalation_recipients'])}\n"
        f"From: {cfg['sender_name']} <{cfg['sender_email']}>\n\n"
        f"As of {r['today']} (response cutoff {r['cutoff']}), the rural-clinic "
        f"survey has {r['responded']} response(s) from {r['sent']} invitation(s) "
        f"({r['response_rate'] * 100:.1f}%), below our "
        f"{cfg['low_response_threshold'] * 100:.0f}% threshold "
        f"(curated list: {r['total']} contacts). We request the Authentic "
        "Consortium's help distributing the survey through its warm-intro "
        "network to lift response volume.\n"
    )


def run(cfg: dict | None = None) -> dict:
    cfg = cfg or config.load()
    r = build_report(cfg)

    # Always write the status report.
    os.makedirs(os.path.dirname(os.path.abspath(cfg["report_path"])), exist_ok=True)
    with open(cfg["report_path"], "w", encoding="utf-8") as fh:
        fh.write(render_markdown(cfg, r))

    # Write the escalation memo only when the threshold is breached.
    if r["escalate"]:
        memo_path = os.path.join(os.path.dirname(cfg["report_path"]), "escalation_memo.md")
        with open(memo_path, "w", encoding="utf-8") as fh:
            fh.write(render_escalation_memo(cfg, r))
        print(f"[report] ESCALATION written -> {memo_path}")

    print(f"[report] {r['responded']} responses / {r['sent']} sent "
          f"({r['response_rate'] * 100:.1f}%) -> {cfg['report_path']}")
    return r


if __name__ == "__main__":
    run()
