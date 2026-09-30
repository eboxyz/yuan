# Setup answers (`intake.json`)

`intake.json` holds one person's answers to the setup questions. The tracker
generator turns it into a personalized job-search tracker: their words go into
the tracker's settings files unchanged, and their choices switch features on
or off. The full definition is
[`tracker-setup/intake.schema.json`](../tracker-setup/intake.schema.json);
examples with made-up people are in
[`tracker-setup/examples/`](../tracker-setup/examples/).

## Two ways to use it

**Build it for someone.** Put their `intake.json` anywhere and run, from this
repository:

```
python3 -m venv .gen && .gen/bin/pip install -q jinja2
.gen/bin/python tracker-setup/scripts/generate_project.py \
  tracker-setup/presets/job-search.json packages/<name> \
  --intake path/to/intake.json --zip
```

This writes `packages/<name>/` and `packages/<name>.zip`. Send them the zip.
They need Claude Code, Python 3 and Postgres (`install.sh` checks for all
three); then they unzip it, open a terminal in the folder, run `claude` and say
hello. The folder's `CLAUDE.md` walks them through the first run: starting
Postgres and the dashboard, drafting their profile from their resume, and
adding more search terms. Their resume stays on their computer. You never need it, and the package
never contains it.

To try a package on your own machine without touching a tracker you already
run, add `--db-name` and `--port` (these override everything else).

**Set it up yourself.** Put `intake.json` (and your resume, if you like) in an
empty folder, run `claude` there and type `/tracker-setup`. It reads the file,
shows a short summary and builds the tracker without asking the setup
questions again.

## What goes where

| Answer | Ends up in |
|---|---|
| `basics.preferred_name` | `CLAUDE.md`, the dashboard title ("Name's Job Search"), the database name `job_search_<name>` |
| `basics.job_finder` (default on) | Whether the job finder, review queue and settings folder are generated. Off also removes the `Queued` stage. |
| `basics.drafting` (default on) | Whether cover-letter drafting is generated. Needs the job finder; if the finder is off, drafting is turned off with a warning. |
| `what_you_want.priorities`, `.tradeoff` | `job_search/criteria.md`, "What matters most (ranked)" and "What I'd give up for #1". The scout requires a strong match to fit #1; check-ins start from these. |
| `what_you_want.*` (others) | `criteria.md`: pay floor and other parts of the package, balance, where and how they work, company size and why, timeline, must-haves, dealbreakers |
| `work_authorization.*` | `criteria.md`, "Work authorization": status, the date it ends (drives check-ins at 90/60/30 days), what they need from an employer. The scout skips postings that rule them out. Never put in drafts unless they ask. |
| `risk.*` | `criteria.md`, "Risk": comfort, runway, dependents, what a layoff would mean. Weighs stability in tiering and check-ins. |
| `where_to_look.titles` | `criteria.md` and `job_search/search_terms.md` (the starter search terms) |
| `where_to_look.*` (others) | `criteria.md`: seniority, industries, companies to favor or skip |
| `job_finder.sources` | Where the finder looks: `company_boards` (Greenhouse and Ashby), `yc`, `hn`, `web` |
| `job_finder.run_size` | Run size: `light`, `standard` or `thorough` |
| `job_finder.pickiness` | `strong_only`, or `strong_and_maybe` (default) |
| `job_finder.drafts` | What gets a draft automatically: `none`, `strong` (default), `strong_with_outreach` (also short direct-outreach emails), `all` |
| `job_finder.daily_run` | `"HH:MM"` (default `"08:00"`) or `"off"`. The first session explains the daily run, shows what it may do without asking, and installs it with their OK (`schedule.sh`). |
| `job_finder.watch_companies` | `job_search/watch_companies.txt`, checked every run |
| `about_you.strengths`, `about_you.links` | `job_search/profile.md` (a starter; the first Claude session fills in the rest from the resume) |
| `about_you.voice_sample` | `job_search/voice.md` |
| `stories` (up to 6, each answering one prompt) | A "raw notes" section of `job_search/proof_bank.md`, unedited, headed by the prompt. In the first session `search-coach` goes through them (at most two follow-ups each); `proof-bank-builder` turns them into full entries. |

The whole file is also copied to `job_search/intake.json` for reference.

The wording of every question, its one-line "why", and the words for each
choice live in the schema (`title`, `description`, `x-labels`), so the setup
page and the generated files say the same thing.

## Rules the generator follows

- Required: `version` (1), `basics.preferred_name`, and at least one title in
  `where_to_look.titles`. Everything else is optional; anything left out uses
  the job-search defaults.
- Problems are listed together in plain words, and nothing is written.
  Unknown fields are reported as warnings and ignored, so a newer setup page
  doesn't break an older generator.
- Free text is copied exactly as typed. Nothing is paraphrased, summarized
  or filled in, and no numbers are added.
