# Email / Survey Outreach Pipeline (US-003)

A reproducible pipeline to distribute the rural-clinic survey and manage
responses, implementing backlog story **US-003 — _Distribute survey and manage
responses_**.

> **Scope note.** This pipeline drives off a **curated contact list** — a CSV of
> clinics we already have **verified emails and attributes** for
> (`contacts.csv`). It does *not* discover or scrape emails; producing that
> curated list (e.g. via the Authentic Consortium's warm-intro network) is an
> upstream step. The pipeline's job is everything after you have the list:
> send → track → follow up → report.

## What it does

```
ingest  ->  send  ->  track  ->  followup  ->  report
(CSV)       (Gmail)   (Form)     (nudges)     (+escalate)
                          ^
                    curated list
```

Everything is keyed off one **source-of-truth SQLite DB** (`data/outreach.db`)
with a per-contact state machine:

```
not_contacted -> sent -> responded
                   \-> bounced
                   \-> opted_out
```

Each survey invitation embeds a **prefilled Google Form link carrying the
clinic id**, so every response maps back to its contact row automatically, with
no manual matching.

## The contact list (`contacts.csv`)

The one required input. A CSV with a header row; **`organization` and `email`
are required**, everything else (`contact_name`, `role_title`, `phone`, `city`,
`state`, `zip`, `category`, `source`) is optional and flows into the matching
contact fields used by the later stages. Headers are case-insensitive and order
doesn't matter; unrecognized columns are ignored.

```
organization,email,contact_name,role_title,phone,city,state,zip,category,source
Virginia Rural Health Association,boconnor@vrha.org,Beth O'Connor,Executive Director,(540) 231-7923,Blacksburg,VA,24060,Rural Health Association,VRHA official website
```

Rows are keyed on **`email`** (one row per address), so a single organization
can carry several contacts and re-running `ingest` is idempotent. Rows missing
an organization or email are skipped and reported by `ingest`.
Unlike the generated `data/` directory (gitignored), `contacts.csv` is committed
so `python run.py all` stays reproducible from a checked-in source — replace the
shipped sample with the real curated list.

## Acceptance-criteria mapping

| US-003 criterion | Where |
| --- | --- |
| Survey in a low-friction tool (Google Forms) | `send.prefilled_link` + the Form itself |
| Sent via warm-intro channel; 1–2 follow-ups scheduled | warm copy in `send.render_email`; `followup` (capped at `max_followups=2`) |
| Response cutoff before FRS deadline (June 24) | `config.response_cutoff`; enforced in `report` |
| Responses logged centrally; low volume flagged for escalation | SQLite source of truth; `report` writes `escalation_memo.md` |

## Quick start

```bash
cd email_pipeline
make setup                 # pip install + create config.yaml from the example
python run.py all          # ingest + report  (no credentials needed)
```

`run.py all` is safe and credential-free: it loads `contacts.csv` into the DB
and prints the status report. Sending requires Google credentials (below).

## Stages

| Command | Needs creds? | Notes |
| --- | --- | --- |
| `python run.py ingest` | no | curated CSV → DB (idempotent) |
| `python run.py send` | no | **dry run** — renders invitations, sends nothing |
| `python run.py send --send` | Gmail | actually sends, advances contacts to `sent` |
| `python run.py track` | Sheets | ingests Google Form responses → `responded` |
| `python run.py followup` | no | **dry run** — lists contacts due for a nudge |
| `python run.py followup --send` | Gmail | sends follow-ups (respects cadence + cap) |
| `python run.py report` | no | status report + escalation memo |
| `python run.py all` | no | ingest + report (safe, no sending) |

## Configuration

Copy `config.example.yaml` → `config.yaml` and fill the `REPLACE_*` values
(Form id, hidden `Clinic ID` entry id, responses Sheet id, sender email, cutoff,
threshold). Omitted keys fall back to `pipeline/config.py:DEFAULTS`.

### Google setup (one time)

1. **Form** — add a short-answer question titled **Clinic ID**; in the Form
   "⋮ → Get pre-filled link", submit a dummy id, and copy the `entry.XXXX` id
   into `survey_clinic_id_entry`. Set `survey_base_url` to the Form's `viewform`
   URL. Link the Form to a responses Sheet and copy its id into
   `survey_responses_sheet_id`.
2. **Gmail / Sheets API** — create an OAuth client (Desktop) in Google Cloud,
   download it to `credentials/gmail_oauth.json`. First `--send`/`track` run does
   the OAuth dance and caches `credentials/gmail_token.json`. Scopes:
   `gmail.send`, `spreadsheets.readonly`.

`config.yaml` and `credentials/` are gitignored — never commit them.

## Compliance & ethics

- **Non-PHI.** Contacts are organizational addresses only; no patient data.
- **CAN-SPAM.** Every message includes a physical address and a one-click
  opt-out. At this list size opt-out replies are handled manually: set the
  contact's `opted_out=1` (it is then excluded from all sends). Sends are
  throttled (`send_throttle_seconds`).
- **Warm-intro first.** Prefer distribution through the Authentic Consortium
  network where possible; cold email is the fallback for curated contacts.

## Layout

```
email_pipeline/
├── run.py                  # CLI entry point
├── Makefile                # convenience targets
├── requirements.txt
├── config.example.yaml
├── contacts.csv            # curated contact list (verified emails + attributes)
├── pipeline/
│   ├── config.py           # config loader + defaults
│   ├── db.py               # SQLite schema, state machine, audit log
│   ├── ingest.py           # stage 1  (curated CSV → DB)
│   ├── send.py             # stage 2  (prefilled link, warm email, Gmail)
│   ├── track.py            # stage 3  (Form responses)
│   ├── followup.py         # stage 4  (scheduled nudges)
│   └── report.py           # stage 5  (status + escalation)
└── data/                   # generated DB + report (gitignored)
```
