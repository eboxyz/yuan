---
name: tracker-setup
description: Set up a local tracker for a search or application pipeline — job hunting, apartment hunting, grad school admissions, sales leads, or similar — with a Postgres database, a dashboard, and optional Claude Code helpers that find candidates and draft materials. If an intake.json (answers from the setup page) is in the folder, it builds a personalized job-search tracker from it; job search otherwise uses a ready-made configuration with no questions asked; every other domain gets a short interview first.
---

# Tracker setup

Generates a complete pipeline tracker — Postgres schema, a thin FastAPI
read/write API, a dashboard, a `start.sh` launcher, and one or more Claude
Code skills — customized to whatever the user is tracking. Everything it
needs lives in this skill's own folder: `presets/` (example
configurations), `templates/`, and `scripts/generate_project.py`. In the
steps below, `SKILL_DIR` means the folder that contains this SKILL.md.

Run this once per project, at the very start.

## Step 1 — make sure this is the right folder

Generated files land in the current directory, so check first:

- If the current directory is the user's home folder, or already contains
  other files (ignore `.claude`, `.git`, `intake.json`, a resume or similar
  background document, and the `CLAUDE.md` and `START_HERE.txt` that come in
  a folder downloaded from the setup page), stop. A downloaded folder is
  meant to be built in place: its starter `CLAUDE.md` is replaced by the
  generated one. Tell them, in plain
  words, that the tracker should live in its own new folder, and offer to
  create one (suggest `~/job-search`, or a name that fits what they're
  tracking). If they agree, create it and use it as the target folder for
  the steps below, then remind them at the end to start Claude Code from
  inside it (`cd <folder> && claude`) so the generated skills are
  available.
- Otherwise continue in the current directory.

## Step 2 — understand the domain

**Setup answers — check this first.** If `intake.json` is in the folder, the
person already answered the setup questions: it's a job search, and nothing
in the rest of this step is asked. Read the file and show a short summary
(their name, the titles, whether the job finder and drafting are on, where it
looks, run size) in five lines or fewer, then go to Step 3. In Step 4, pass
`--intake intake.json`. If the generator reports problems, ask one plain
question per problem (e.g. "What job titles should it look for?"), write the
answer into `intake.json` in their words, and run it again. Mention any
warnings in one line.

**Job search preset — check this first, before asking anything.** If the
user's answer to "what are you tracking" is job search / job hunting / job
applications (however they phrase it), skip the rest of this step
entirely: use `presets/job-search.json` as-is as the config and go
straight to Step 3. Don't ask any of the questions below for this domain —
they're already decided and match a working, tested tracker. Only deviate
from the preset if the user explicitly asks for something different (e.g.
"call it 'interviews' instead" or "skip the cover-letter drafter") — apply
just that one change, don't turn it into a fresh round of questions.

For every other domain, run the full interview below.

Ask the user (conversationally, or with `AskUserQuestion` for the
multiple-choice-shaped ones) what they're tracking. Look at
`presets/*.json` first for a domain that's close to theirs — reusing one as
a starting point and adjusting it is faster and less error-prone than
building a config from scratch. You need:

**Core**

- What is this project tracking, in a couple words? (→ `project_name`)
- What do you call one of these things, singular and plural? (e.g.
  "listing"/"listings", "lead"/"leads") (→ `entity_singular`,
  `entity_plural`)
- What are the two main identifying fields for one of these? (e.g.
  company+role, building+unit, school+program) (→ `primary_field`/
  `primary_label`, `secondary_field`/`secondary_label` — field names should
  be short lowercase_snake_case; labels are the human-readable version)
- What are the source types? (e.g. "Self-applied", "Referral", "Inbound") —
  a short list (→ `source_type_options`)

**Stages** — ask for the full ordered list of stages this moves through,
then which one means:

- "just found, not yet committed" — only if there's a scout agent (→
  `queued_stage`)
- "officially in the pipeline" baseline (→ `baseline_stage`)
- the best outcome (→ `success_stage`)
- closed-without-success — can be more than one (→ `closed_stages`)
  Everything else in the list becomes "in progress" automatically — don't
  ask the user to classify every stage by hand.

**Optional axes** — ask about each, skip the ones that don't apply:

- A numeric value axis (comp, rent, tuition, deal size, ...)? → `has_value`
  - `value_label` (`value_field_prefix` can default from the label).
- A free-text category for filtering (industry, neighborhood, program
  type, ...)? → `has_category` + `category_label`.
- A third-party contact/intermediary concept (recruiter, broker, admissions
  contact, ...)? → `has_contact` + `contact_singular`/`contact_plural` +
  `contact_org_label` (what org the contact belongs to, e.g. "Agency").

**Scout agent** — does this domain have a discoverable external source
worth searching automatically (job boards, listing sites, directories), or
is it manual-entry only (e.g. grad school applications)? → `has_scout_agent`.
If yes:

- What do you call the source? (e.g. "job board", "listing site") →
  `source_label`.
- Does the agent draft something per candidate (cover letter, personal
  statement, intro message), or just stage the row? → `artifact_enabled`
  - `artifact_label`.

**Branding/mechanics** (all have sensible defaults — don't belabor these):
`app_display_name`, `tagline`, `icon` (a Material Symbols name), `db_name`,
`port`, `config_dir_name`.

Write the answers to `config.json` in the project folder.
`scripts/generate_project.py` fills in any field you omit with a reasonable
default, so don't force the user through every field if a default is fine.
If `has_scout_agent` is true, remember the scout only reads public pages —
it never logs in, submits, or creates accounts.

## Step 3 — check Postgres

Run `pg_isready`. Exit code 0 means it is running. If it isn't, help the
user install and start it, then re-check before continuing:

- **macOS**: `brew install postgresql@16 && brew services start postgresql@16`
  (no Homebrew: https://brew.sh, or the Postgres.app installer)
- **Linux**: `sudo apt install postgresql && sudo systemctl start postgresql`
- **Windows**: use WSL, then follow the Linux steps.

Don't move on until `pg_isready` succeeds — `start.sh` needs it. Don't just
let it fail later with a cryptic "could not connect to server".

## Step 4 — generate

```
python3 -m venv .venv
.venv/bin/pip install -q jinja2
.venv/bin/python SKILL_DIR/scripts/generate_project.py <config> .
```

`<config>` is `SKILL_DIR/presets/job-search.json` for a job search (add
`--intake intake.json` when that file is present), or the `config.json` you
wrote in Step 2. If something is already listening on the config's port
(8420 for a job search; check with `lsof -iTCP:8420 -sTCP:LISTEN`), usually
another tracker, add `--port` with the next free port. (Replace `.` with the new folder if
Step 1 created one, and run the venv commands inside it.) This writes
`db/`, `api/`, `dashboard/`, `start.sh`, a `README.md`, optionally a
settings folder, the generated skills under `.claude/skills/`, and a
`CLAUDE.md` that tells future Claude sessions in this folder how the tracker
works. It never touches `tracker-setup` itself.

## Step 5 — first run, then what to do next

Read the generated `CLAUDE.md` now (this session started before it existed,
so it isn't loaded yet) and walk through its **First run** section with them,
skipping the Postgres check you already did. It covers starting the
dashboard, the profile draft from their resume, search terms, and adding a
first row. Then wrap up, short and non-technical. Read the file list the generator printed
so the skill names below match what was actually generated. Explain that:

1. **To start the tracker**, run `./start.sh` in a second terminal (leave
   this Claude session open). The first run creates the database and
   installs what it needs; after that it just starts. It prints the
   dashboard address (`http://localhost:<port>/`).
2. **To track things**, just tell Claude what happened and it will update
   the database.
3. **If a scout agent was generated**, they first fill in the files in the
   settings folder (`criteria.md`, `search_terms.md`, and `profile.md` /
   `voice.md` if drafting is enabled). Then the scout skill searches public
   sources and stages candidates for review on the dashboard's queue page.
   It never submits anything or creates an account — the user does that
   themselves. If a proof-bank builder was generated, suggest running it
   once before the scout.
4. The insights skill gives a fresh read on the pipeline any time there's
   data.

For a job search specifically, the generated skills are
`application-insights`, `application-scout-agent`, `cover-letter`,
`proof-bank-builder` and `search-coach`, and the queue page is at http://localhost:8420/queue.html.

## Notes

- Runtime dependencies of the generated tracker are only `psycopg`,
  `fastapi` and `uvicorn`, installed into the project's own `.venv` by
  `start.sh`. `jinja2` is only needed to run the generator.
- Don't hand-edit files under `SKILL_DIR/templates/` while setting up one
  user's project. Those are the shared source for every future run; fix
  bugs there, not in a generated copy.
- Importing an existing spreadsheet isn't templated — columns vary too much.
  Once the user has a real file, write a one-off import script for it.
