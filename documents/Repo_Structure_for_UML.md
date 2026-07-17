# Repository Structure — Reference for UML Diagrams

**Repo:** CS5934 — Application to Prevent Predictable Hospitalizations (Team 5)
**Purpose:** A structural distillation of the *current* repo so UML diagrams (component,
class/module, sequence, state, ERD) reflect what actually exists. Generated 2026-06-28.

> **Scope note:** Only `email_pipeline/` (US-003) contains executable code today. Everything
> else in the repo is planning/documents or a deployable survey script. Diagram the pipeline
> as the realized system; model the rest as *planned* components.

---

## 1. Top-level file tree (actual)

```
CS5934/
├── CLAUDE.md                                  # repo guidance
├── documents/                                 # planning artifacts (non-code)
│   ├── Product_Backlog.docx                   # 26 user stories
│   ├── Team 5 CS5934 Project Definition.docx  # Inception Report
│   ├── Va Tech Team Roadmap to Success.docx   # 7-phase roadmap
│   ├── va_rural_clinic_contacts.xlsx          # ~995-row contact list (US-002)
│   ├── rural_healthcare_needs_assessment_form_clean.gs  # survey builder (US-001, 838 lines)
│   ├── git-helper-sheet.md
│   ├── Sprint1_Submission.md                  # Sprint 1 report
│   └── Repo_Structure_for_UML.md              # (this file)
└── email_pipeline/                            # US-003 — the only code module
    ├── run.py                                 # CLI entrypoint
    ├── Makefile                               # convenience targets
    ├── requirements.txt                       # deps
    ├── config.example.yaml                    # config template
    ├── contacts.csv                           # curated send list (input)
    ├── .gitignore
    ├── README.md
    ├── pipeline/                              # package
    │   ├── __init__.py
    │   ├── config.py                          # config loader + DEFAULTS
    │   ├── db.py                              # SQLite schema + data access
    │   ├── ingest.py                          # stage 1
    │   ├── send.py                            # stage 2
    │   ├── track.py                           # stage 3
    │   ├── followup.py                        # stage 4
    │   └── report.py                          # stage 5
    └── data/                                  # generated (gitignored)
        ├── outreach.db                        # SQLite source of truth
        ├── status_report.md                   # report output
        └── escalation_memo.md                 # escalation output
```

---

## 2. Component diagram (email_pipeline)

Modules and their dependencies. `db.py` and `config.py` are the shared foundation; every
stage depends on both. `run.py` orchestrates the stages.

```mermaid
flowchart TD
    cli["run.py<br/>(CLI orchestrator)"]
    subgraph pkg["pipeline package"]
        config["config.py"]
        db["db.py"]
        ingest["ingest.py"]
        send["send.py"]
        track["track.py"]
        followup["followup.py"]
        report["report.py"]
    end

    csv[("contacts.csv")]
    sqlite[("data/outreach.db")]
    reports[("status_report.md<br/>escalation_memo.md")]
    gmail{{"Gmail API"}}
    forms{{"Google Forms"}}
    sheets{{"Google Sheets"}}

    cli --> ingest & send & track & followup & report
    ingest --> db
    send --> db
    track --> db
    followup --> db
    report --> db
    ingest -. uses .-> config
    send -. uses .-> config
    track -. uses .-> config
    followup -. uses .-> config
    report -. uses .-> config

    csv --> ingest
    db <--> sqlite
    send --> gmail
    send -. prefilled link .-> forms
    forms -. responses .-> sheets
    sheets --> track
    report --> reports
```

**External dependencies (from `requirements.txt`):** PyYAML, google-api-python-client,
google-auth-oauthlib, google-auth-httplib2, gspread. Core (ingest/db/report/run) uses only
the Python stdlib; only `send`/`track`/`followup` need Google credentials.

---

## 3. Module / "class" diagram (functions per module)

The codebase is module-functional (no Python classes). For a UML *class diagram*, model each
module as a class-like unit with its public functions as operations. Signatures are exact.

```mermaid
classDiagram
    class config {
        +DEFAULTS: dict
        +load(path) dict
        +cutoff_date(cfg) date
        -_parse_simple_yaml(text) dict
    }
    class db {
        +STATUSES: tuple
        +SCHEMA: str
        +connect(path) Connection
        +init(conn) void
        +session(path) ctx
        +upsert_contact(conn, row) void
        +set_status(conn, id, status, ts, **fields) void
        +log_event(conn, id, ts, type, channel, detail) void
        +all_contacts(conn) list~Row~
        +sendable(conn) list~Row~
        +status_counts(conn) dict
    }
    class ingest {
        +COLUMN_MAP: dict
        +run(cfg) dict
        -_read_csv(path) list~dict~
    }
    class send {
        +prefilled_link(cfg, contact_id) str
        +render_email(cfg, contact) tuple
        +run(cfg, dry_run, limit) dict
        -_gmail_service(cfg)
        -_send_via_gmail(service, sender, to, subject, body)
    }
    class track {
        +fetch_responses(cfg) list~dict~
        +run(cfg, responses) dict
        -_open_sheet(cfg)
    }
    class followup {
        +due(contact, cfg, today_days) bool
        +run(cfg, dry_run) dict
        -_days_since(iso_ts) float
    }
    class report {
        +build_report(cfg) dict
        +render_markdown(cfg, r) str
        +render_escalation_memo(cfg, r) str
        +run(cfg) dict
        -_coverage(conn) dict
    }
    class run_cli {
        +main() void
    }

    run_cli ..> ingest
    run_cli ..> send
    run_cli ..> track
    run_cli ..> followup
    run_cli ..> report
    ingest ..> db
    ingest ..> config
    send ..> db
    send ..> config
    track ..> db
    track ..> config
    followup ..> db
    followup ..> config
    report ..> db
    report ..> config
```

---

## 4. Data model / ERD (SQLite — `db.py`)

Two tables. `events` references `contacts` (append-only audit log). This is the source of
truth all stages read/write.

```mermaid
erDiagram
    contacts ||--o{ events : "logs"

    contacts {
        INTEGER id PK
        TEXT category
        TEXT organization "NOT NULL"
        TEXT contact_name
        TEXT role_title
        TEXT email "UNIQUE"
        TEXT phone
        TEXT city
        TEXT state
        TEXT zip
        TEXT source
        TEXT enriched_email
        TEXT status "default not_contacted"
        INTEGER opted_out "default 0"
        INTEGER bounced "default 0"
        TEXT sent_at
        TEXT responded_at
        INTEGER followups_sent "default 0"
        TEXT last_contact_at
        TEXT notes
    }
    events {
        INTEGER id PK
        INTEGER contact_id FK
        TEXT ts "NOT NULL"
        TEXT event_type "NOT NULL"
        TEXT channel "email|warm_intro|phone|form|system"
        TEXT detail
    }
```

> Confirm exact column set against `email_pipeline/pipeline/db.py` lines 15–53 before
> publishing; fields above reflect the committed schema.

---

## 5. State machine (per-contact lifecycle — `db.STATUSES`)

```mermaid
stateDiagram-v2
    [*] --> not_contacted : ingest
    not_contacted --> sent : send (Gmail)
    sent --> responded : track (Form match)
    sent --> sent : followup (nudge, cap 2)
    not_contacted --> bounced : invalid address
    sent --> bounced : delivery failure
    not_contacted --> opted_out : opt-out
    sent --> opted_out : opt-out
    responded --> [*]
    bounced --> [*]
    opted_out --> [*]
```

`STATUSES = ("not_contacted", "sent", "responded", "bounced", "opted_out")`

---

## 6. Sequence diagram (`python run.py all` and full campaign)

```mermaid
sequenceDiagram
    actor Team as Data Scientist
    participant CLI as run.py
    participant I as ingest
    participant DB as db / outreach.db
    participant S as send
    participant G as Gmail / Forms
    participant T as track
    participant Sh as Sheets
    participant F as followup
    participant R as report

    Team->>CLI: python run.py all
    CLI->>I: run(cfg)
    I->>DB: upsert_contact() per CSV row
    CLI->>R: run(cfg)
    R->>DB: status_counts(), _coverage()
    R-->>Team: status_report.md (+ escalation_memo.md if low)

    Note over Team,G: credentialed stages (run separately)
    Team->>CLI: python run.py send --send
    CLI->>S: run(cfg, dry_run=False)
    S->>DB: sendable()
    S->>G: send prefilled-link email
    S->>DB: set_status(sent)
    G-->>Sh: respondent submits Form
    Team->>CLI: python run.py track
    CLI->>T: run(cfg)
    T->>Sh: fetch_responses()
    T->>DB: set_status(responded) on Clinic ID match
    Team->>CLI: python run.py followup --send
    CLI->>F: run(cfg, dry_run=False)
    F->>DB: due() check, set_status / followups_sent++
    F->>G: send nudge (cap 2)
```

---

## 7. Pipeline stage summary (for use-case / activity diagrams)

| Stage | Module | CLI command | Reads | Writes | Needs creds |
| --- | --- | --- | --- | --- | --- |
| Ingest | `ingest.py` | `run.py ingest` | `contacts.csv` | `contacts` table | No |
| Send | `send.py` | `run.py send [--send]` | `contacts` (sendable) | `contacts.status`, `events` | Gmail (live only) |
| Track | `track.py` | `run.py track` | Google Sheet responses | `contacts.status`, `events` | Sheets |
| Follow-up | `followup.py` | `run.py followup [--send]` | `contacts` (due) | `contacts.followups_sent`, `events` | Gmail (live only) |
| Report | `report.py` | `run.py report` | `contacts`, `events` | `status_report.md`, `escalation_memo.md` | No |
| All | `run.py` | `run.py all` | (ingest + report) | DB + reports | No |

---

## 8. Planned (not-yet-built) components — model as future

For a forward-looking architecture/component diagram, these are *planned* per the backlog
(Sprint 2–3) and have **no code yet**. Mark them distinctly (dashed / «planned»):

- **SDoH ingestion** (US-009) — pulls CDC PLACES / HRSA / Census / CMS (see data-source catalog US-006)
- **Synthetic clinical loader** (US-010) → clinical schema
- **Geographic join** (US-012) — county FIPS / ZCTA community→patient join (core challenge)
- **Feature engineering + bias screening** (US-013/014)
- **Modeling** (US-015–018) — logistic baseline, advanced models, PR-AUC + calibration, rurality fairness
- **Decision support** (US-019–022) — risk tiering (WHO), explainability (WHY), intervention mapping (WHAT NEXT), HITL override
- **Reproducible single-command pipeline** (US-023)

> These map to the use-case diagram in `Sprint1_Submission.md` §4 (UC3–UC12), which already
> distinguishes built (Sprint 1) vs planned (Sprint 2–3) use cases.
