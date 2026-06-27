#!/usr/bin/env python3
"""US-003 outreach pipeline - single entry point.

Examples:
    python run.py ingest            # load the curated contact list into the DB
    python run.py send              # DRY RUN: render invitations, send nothing
    python run.py send --send       # actually send via Gmail
    python run.py track             # ingest Google Form responses
    python run.py followup          # DRY RUN: list contacts due for a nudge
    python run.py followup --send   # actually send follow-ups
    python run.py report            # central status + escalation check
    python run.py all               # ingest + report (safe, no sending)
"""

from __future__ import annotations

import argparse

from pipeline import config, ingest, send, track, followup, report


# Parse the stage argument and dispatch to the matching pipeline module.
def main() -> None:
    # Define the CLI: one positional stage plus a few shared flags.
    parser = argparse.ArgumentParser(description="US-003 survey outreach pipeline")
    parser.add_argument(
        "stage",
        choices=["ingest", "send", "track", "followup", "report", "all"],
    )
    parser.add_argument("--config", help="path to config.yaml")
    parser.add_argument("--send", action="store_true",
                        help="actually send (send/followup default to dry-run)")
    parser.add_argument("--limit", type=int, help="cap contacts processed (send)")
    args = parser.parse_args()

    cfg = config.load(args.config)
    dry = not args.send

    # Run the requested stage.
    if args.stage == "ingest":
        ingest.run(cfg)
    elif args.stage == "send":
        send.run(cfg, dry_run=dry, limit=args.limit)
    elif args.stage == "track":
        track.run(cfg)
    elif args.stage == "followup":
        followup.run(cfg, dry_run=dry)
    elif args.stage == "report":
        report.run(cfg)
    elif args.stage == "all":
        # Safe, credential-free chain: load the list -> status report.
        ingest.run(cfg)
        report.run(cfg)


if __name__ == "__main__":
    main()
