# Yuan: technical documentation

## How it works

There are two ways in, and both end in the same generator:

1. **The setup page** (`portal/`) collects a person's answers and builds a
   zip in their browser: `intake.json`, their resume, the `tracker-setup`
   skill, a starter `CLAUDE.md` and `START_HERE.txt`. When they open the
   folder with Claude, the starter `CLAUDE.md` has Claude run the skill,
   which builds the tracker in place and replaces the starter with the real
   `CLAUDE.md`.
2. **`/tracker-setup` directly**, after `install.sh`, in an empty folder
   (with or without an `intake.json`).

`/tracker-setup` (the skill in `tracker-setup/`) renders Jinja templates using
a preset from `presets/` (`job-search.json` by default), plus the person's
answers when there are any, and writes a complete project into the folder:

```
db/schema.sql          tables, stage-history trigger
api/server.py          FastAPI read/write API, also serves dashboard/
dashboard/             static pages, no build step
start.sh               creates the DB on first run, then starts the server
CLAUDE.md              how this tracker works, for Claude; includes a first-run checklist
.claude/hooks/         checkin.py, run at session start (job search only; see below)
job_search/            criteria, search terms, profile, proof bank, scout state
.claude/skills/        application-insights, application-scout-agent, cover-letter,
                       proof-bank-builder, search-coach, resume-builder
schedule.sh            turns the daily scout run on or off (run_daily.sh is the run)
```

Runtime dependencies of the generated project: `psycopg`, `fastapi`,
`uvicorn` (installed into the project's `.venv` by `start.sh`). `jinja2` is
only used by the generator.

## Setup page

`portal/` is a single static page (plain HTML, CSS and JavaScript, no
framework, no build tool). It loads only its own files, including the
self-hosted Plus Jakarta Sans font, and makes no outside requests. Answers
autosave to the browser's `localStorage`; the resume is kept in memory and
only goes into the download. The question wording comes from
`tracker-setup/intake.schema.json`, so the page and the generated tracker say
the same thing. `portal/lib.js` holds the zip writer (store-only, CRC-32,
Unix permissions), the validator (the same rules and messages as
`scripts/intake.py`) and the package builder, with no page code, so it runs
under Node for testing. `portal/skill-bundle.js` is generated from
`tracker-setup/` by `python3 portal/build.py` (`--check` reports a stale
bundle). Host the folder on any static host.

## Installer

`install.sh` checks for Claude Code, Python 3.9+ and Postgres, offers to
install anything missing (Homebrew on macOS, apt on Linux), and copies
`tracker-setup/` to `~/.claude/skills/`. Flags: `--yes`, `--uninstall`.
On Linux it also offers to create a Postgres role for your user, since the
tracker connects over the local socket as you.

Generate manually instead:

```
python3 -m venv .venv && .venv/bin/pip install jinja2
.venv/bin/python tracker-setup/scripts/generate_project.py tracker-setup/presets/job-search.json .
```

## Other domains (experimental)

The generator is domain-agnostic. `presets/` also has `apartment-hunt`,
`grad-school-apps` and `sales-leads`, and `/tracker-setup` runs a short
interview for anything that isn't a job search, using the closest preset as
a starting point. These are less tested than the job-search preset. To
generate one manually, pass its file to the generator instead of
`job-search.json`.

## Configuration (`presets/job-search.json`)

| Field | Meaning |
|---|---|
| `stages` | Ordered pipeline stages |
| `queued_stage` | Where scout-found candidates land, before you commit |
| `baseline_stage` | "Officially in the pipeline" (funnel baseline) |
| `success_stage` | Best outcome |
| `closed_stages` | Ended without success (first one is used by Dismiss) |
| `source_type_options` | Choices for how an application originated |
| `has_value`, `value_label` | Numeric axis (compensation) and its label |
| `has_category`, `category_label` | Free-text filter axis (industry) |
| `has_contact`, `contact_*` | Third-party contact concept (recruiters) |
| `has_scout_agent`, `artifact_enabled` | Scout agent, and per-candidate drafting |
| `scout_sources` | Where the scout looks: any of `greenhouse`, `ashby`, `yc`, `hn`, `web` (default `["web"]`; the job-search preset uses the first four) |
| `scout_budget_preset` | `light`, `standard` (default) or `thorough`. Sets the numbers below; any explicit `scout_*` key overrides it. |
| `scout_candidates_target`, `scout_candidates_cap`, `scout_jd_fetch_cap`, `scout_terms_per_run`, `scout_subagents_per_run` | The per-run budget. Presets: light 5 / 8 / 12 / 4, standard 10 / 15 / 25 / 8, thorough 15 / 25 / 50 / all (target A-tier candidates / hard cap / full-posting fetches / web-search terms). |
| `scout_tier_mode` | `strong_and_maybe` (default) queues A- and B-tier matches; `strong_only` queues A-tier only |
| `artifact_scope` | What gets drafted automatically: `none` (only on request), `strong` (A-tier, default when drafting is on) or `all` |
| `scout_outreach_mode` | `true` adds outreach detection and a short "direct outreach" email mode to the drafter (default `false`) |
| `watch_companies` | Companies whose job boards are checked every run (written to `watch_companies.txt`) |
| `has_coaching` | Job search: the `search-coach` skill, criteria-first `criteria.md`, `reflections.md`, and the session-start check-in hook |
| `daily_run`, `skip_if_waiting` | Daily scheduled scout run time (`"off"` or `"HH:MM"`) and the review-queue size at which a day is skipped (default 15) |
| `stage_notes` | Optional one-line meaning per stage, written into `CLAUDE.md` (e.g. what counts as `Onsite`) |
| `db_name`, `port`, `config_dir_name` | Database name, dashboard port, settings folder |

The generator validates that `baseline_stage`, `success_stage`,
`closed_stages` and `queued_stage` are all members of `stages`, and fills any
omitted field with a default. To customize, copy the preset, edit it, and run
the generator against your copy.

Generator command line:

```
generate_project.py <config.json> <target_dir> [--intake intake.json] [--db-name NAME] [--port N] [--zip]
```

`--intake` merges a person's setup answers over the config (see
[intake.md](intake.md)); `--db-name` and `--port` override both; `--zip` also
writes `<target_dir>.zip` without `.venv` or caches, with file permissions
kept.

## Coaching and check-ins (job search)

`search-coach` handles the first-run reflection on what the person wants,
coaching their story notes, and check-ins. Check-ins are started by
`.claude/hooks/checkin.py`, a `SessionStart` hook registered in the tracker's
`.claude/settings.json`. It prints one line into Claude's context only when a
check-in is due, and nothing otherwise. Triggers are counted since the last
entry in `job_search/reflections.md`:

- **Always:** the first session after setup; an offer; work authorization
  ending within 90, 60 or 30 days, or already past.
- **At most weekly:** first final round; 3+ rejections; 10+ applications in 7
  days; 14+ days without activity.

It reads only the tracker's own database and files, never fails loudly, and
can be tested with `--now 'YYYY-MM-DD HH:MM'`. Claude Code asks the person to
trust the folder before any hook runs.

## Daily run

For trackers with the job finder, `schedule.sh install [HH:MM] | remove |
status | permissions` turns a daily scout run on or off: a launchd agent in
`~/Library/LaunchAgents` on macOS (a run missed during sleep happens at wake),
or one tagged line in the crontab on Linux. `install` records the current
`PATH` and the `claude` path in `.claude/daily_run.env`, because scheduled
jobs start with a bare environment.

`run_daily.sh` skips the day, and logs why, when the first run isn't finished,
Postgres isn't running, or 15 or more (`skip_if_waiting`) are already waiting
for review. Otherwise it runs `claude -p "/<entity>-scout-agent …"` with
`--permission-mode dontAsk`, `--max-turns 200` and an `--allowedTools` list
limited to file tools, web search and fetch, skills, `psql` on the tracker's
own database, and the scout's own fetch tools. Everything else is denied. The
list applies only to the unattended run, not to interactive sessions.
`JST_DAILY_RUN=1` keeps the session-start check-in quiet during it. Output goes
to `logs/daily_run.log`. Config: `daily_run` (`"off"` or `"HH:MM"`; the
job-search preset uses `"08:00"`).

## Resume builder

`resume-builder` (job search with drafting) is offered once the story bank has
three full entries. It asks for consent, proposes changes section by section
as before → after (facts only from their resume, profile, story bank or their
answers; it asks for numbers and never fills them in), saves the approved
content to `job_search/resume/resume_content.md`, lets them pick an accent
color, and has a subagent fill `resume_template.html` (one column, real text,
system fonts, no images or tables, so applicant tracking systems can read it).
`render_pdf.sh` prints it to PDF with a headless Chromium-based browser, or
explains Print to PDF. `phrasing_guide.md` holds the phrasing patterns, with
invented examples only.

## Data model

`applications` holds one row per opportunity; `application_notes` is the running notes log (named after your entity, e.g. `listing_notes`); `stage_history` is appended
automatically by a trigger whenever `current_stage` changes, so it is never
edited by hand. `scout_runs` logs each scout run's volume and cap hits.

## The scout agent

Searches public sources within a fixed per-run budget, stages candidates as
`Queued` rows, and holds overflow in `job_search/overflow_backlog.jsonl`. Hard
rules baked into its skill: never submit an application, never create an
account, never enter personal data into an external form, and never log in
anywhere.

### Sources and their tools

For the job sources, the generated project includes small fetch tools in
`.claude/skills/application-scout-agent/tools/` (plain Python 3.9+, standard
library only). They are fetchers and keyword filters; the skill still decides
what is a good match. Each prints JSON lines, hides postings already in
`reviewed_postings.jsonl` and companies already in your tracker (`--all` shows
them), and shares the filters `--include`, `--exclude`, `--location` and
`--limit`.

| Source | Tool | What it reads | Notes |
|---|---|---|---|
| `greenhouse`, `ashby` | `boards.py` | Companies' public job-board APIs | `lookup` finds a company's board from its name and caches it in `known_boards.json`. Greenhouse hits are accepted only if the board's own name matches. Ashby returns no company name, so its hits are marked `verified: false`. Misses are recorded with the names tried and not re-probed for 30 days. `sweep` checks every cached board plus `watch_companies.txt`; `jobs` checks one company; `describe` prints one posting's full text. |
| `yc` | `yc.py` | Y Combinator's public job listing pages | Each page lists only the ~40 newest postings, so it combines roles and locations. It reads JSON embedded in the page; if YC changes that, the tool says so and exits 2. |
| `hn` | `hn.py` | The monthly "Ask HN: Who is hiring?" thread (public Algolia API) | Each top-level comment is a posting. Comments with an email or an invitation to write directly are flagged `outreach`. Company and title are best-effort guesses from the first line. |
| `web` | none | Ordinary web search by the agent | Results can be stale, so the skill checks a company's live board before trusting a snippet. |

The tools make only plain `GET` requests to five public hosts
(`boards-api.greenhouse.io`, `api.ashbyhq.com`, `hn.algolia.com`,
`news.ycombinator.com`, `www.ycombinator.com`), identify themselves with a
`User-Agent`, and space their requests out. They send no credentials and
follow no login flows. If the tracker's database can't be read, they say so and
carry on without hiding tracked companies.

### Not included

Sources that require you to be logged in are deliberately not supported.

## API reference

The generated tracker serves a small JSON API next to its dashboard. `<things>` is
the plural entity name from your config (for a job search: `applications`).

| Route | What it does | Present when |
|---|---|---|
| `GET /api/<things>` | All rows, newest first (with the contact's name if enabled) | always |
| `POST /api/<things>/{id}/set-stage` | Body `{"stage": "..."}`. Must be one of the configured stages (else 400). Stage history is recorded by a database trigger. | always |
| `POST /api/<things>/{id}/schedule` | Body `{"next_step": "...", "next_step_date": "YYYY-MM-DD"}`. Send both as `null` to clear. | always |
| `GET/POST /api/<things>/{id}/notes` | Running notes for one row. Each note records the stage it was written in (`stage_at_time`). Notes are add-only for now. | always |
| `GET /api/upcoming` | Rows with a next-step date, soonest first | always |
| `GET /api/stats/funnel`, `timeline`, `source-types`, `time-in-stage`, `insights` | Numbers behind the Overview page | always |
| `GET /api/stats/value` | Value axis (e.g. compensation) for rows that have one | `has_value` |
| `GET /api/stats/<contacts>` | Rows per contact (e.g. recruiter) | `has_contact` |
| `GET /api/queue`, `POST .../mark-committed`, `POST .../dismiss` | Candidates the scout found, and moving them on | `has_scout_agent` |
| `POST .../request-<artifact>`, `POST .../reveal-<artifact>`, `GET .../download-<artifact>` | Ask for a draft, show it in your file manager, or download it. Downloads only serve files inside the drafts folder. | scout + drafting |

## Local security

The tracker holds private information (people hide their job search), so the local API is locked down:

- **No CORS.** The dashboard is served by the same app, so nothing needs cross-origin access. Other websites you visit cannot read your tracker's data from `localhost`.
- **Host allow-list.** Only `localhost` and `127.0.0.1` are accepted as the `Host`, which stops DNS-rebinding attacks.
- **Cross-site writes are refused.** Any POST/PUT/PATCH/DELETE carrying an `Origin` that differs from the tracker's own address (including `Origin: null` and another port on localhost), or `Sec-Fetch-Site: cross-site`, gets a 403. Requests with no `Origin`, such as `curl`, are allowed.
- **Localhost only.** `start.sh` runs the server on the default `127.0.0.1`. Don't change it to `0.0.0.0`: the API has no login.
- **Note text is stored as typed** and always shown as plain text in the dashboard.

## Troubleshooting

- **`pg_isready` fails / `start.sh` says Postgres isn't running:** start it
  (`brew services start postgresql@16`, `sudo systemctl start postgresql`, or
  open Postgres.app).
- **`createdb: role "<you>" does not exist` (Linux):**
  `sudo -u postgres createuser --superuser $USER`.
- **Port 8420 in use:** change `port` in your config and regenerate, or edit
  the port in `start.sh`.
- **`/tracker-setup` not found in Claude Code:** re-run `./install.sh` and
  restart `claude`; the skill lives at `~/.claude/skills/tracker-setup/`.
- **Uninstall:** `./install.sh --uninstall` removes the skill. Your tracker
  folder and database are yours to delete (`dropdb job_search_tracker`).
