#!/usr/bin/env python3
"""Decides whether Claude should open this session with a short check-in on
what the person wants from their search. Runs as a Claude Code SessionStart
hook (see ../settings.json): prints one line when a check-in is due, nothing
otherwise.

It decides *when*; the search-coach skill decides *what to ask*. Triggers,
counted since the last check-in logged in reflections.md:
  always   the first session after setup; an offer; work authorization ending
           within 90/60/30 days (or already past)
  weekly   first final round; 3+ rejections; 10+ applications in 7 days;
           14+ days without activity (at most one of these check-ins per 7 days)

Reads only this tracker's database and files, sends nothing anywhere, and
never fails loudly: on any problem it prints nothing.

    checkin.py [--today YYYY-MM-DD] [--now 'YYYY-MM-DD HH:MM']   (for testing)
"""
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
FLOOR_DAYS = 7
DEADLINE_STEPS = (30, 60, 90)
ENTRY = re.compile(r"^## (\d{4}-\d{2}-\d{2})(?: (\d{1,2}:\d{2}))?", re.M)
AUTH_UNTIL = re.compile(r"Authorized until:\**\s*(\d{4}-\d{2}-\d{2})")


def sql_str(s):
    return "'" + str(s).replace("'", "''") + "'"


def entries(text):
    """Check-in times from reflections.md headings ('## 2026-10-03 14:05 — ...').
    A heading without a time counts as the start of that day."""
    out = []
    for day, hm in ENTRY.findall(text):
        try:
            out.append(datetime.datetime.fromisoformat(f"{day} {hm or '00:00'}"))
        except ValueError:
            continue
    return out


def reasons_due(cfg, now, reflections_text, criteria_text, db):
    """Returns (urgent, weekly, last) where urgent/weekly are lists of reasons.
    `db(sql)` returns psql -At output or raises."""
    times = entries(reflections_text)
    if not times:
        return [], [], None  # setup's first run hasn't been logged yet; CLAUDE.md covers it
    last = max(times)
    urgent, weekly = [], []
    if len(times) == 1:
        urgent.append("this is the first session since setup")

    m = AUTH_UNTIL.search(criteria_text)
    if m:
        try:
            until = datetime.date.fromisoformat(m.group(1))
            days_left = (until - now.date()).days
            if days_left < 0 and last.date() <= until:
                urgent.append(f"the work authorization date in criteria.md ({until}) has passed; ask whether it has been updated")
            else:
                for step in DEADLINE_STEPS:
                    if 0 <= days_left <= step and last.date() < until - datetime.timedelta(days=step):
                        urgent.append(f"work authorization ends in {days_left} days ({until})")
                        break
        except ValueError:
            pass

    since = sql_str(last.isoformat(sep=" ", timespec="minutes"))
    week_ago = sql_str((now - datetime.timedelta(days=7)).isoformat(sep=" ", timespec="minutes"))
    t, n = cfg["table"], cfg["notes_table"]
    stage = lambda key: sql_str(cfg[key]) if cfg.get(key) else "NULL"
    try:
        row = db(f"""
            SELECT
              count(*) FILTER (WHERE stage = {stage('success_stage')} AND changed_at > {since}),
              count(*) FILTER (WHERE stage = {stage('final_round_stage')} AND changed_at > {since}),
              count(*) FILTER (WHERE stage = {stage('final_round_stage')} AND changed_at <= {since}),
              count(*) FILTER (WHERE stage = {stage('rejected_stage')} AND changed_at > {since}),
              count(*) FILTER (WHERE stage = {stage('baseline_stage')} AND changed_at > {week_ago}),
              (SELECT to_char(greatest(
                  (SELECT max(changed_at) FROM stage_history),
                  (SELECT max(created_at) FROM {n}),
                  (SELECT max(created_at) FROM {t})), 'YYYY-MM-DD'))
            FROM stage_history""")
        offers, finals_new, finals_before, rejections, applied_week, last_activity = row.split("|")
        if int(offers):
            urgent.append("an offer was recorded; compare it with their ranked priorities")
        if int(finals_new) and not int(finals_before):
            weekly.append("they reached their first final round")
        if int(rejections) >= 3:
            weekly.append(f"{rejections} rejections since the last check-in")
        if int(applied_week) >= 10:
            weekly.append(f"{applied_week} applications in the last 7 days")
        quiet_since = datetime.date.fromisoformat(last_activity) if last_activity else last.date()
        quiet_days = (now.date() - max(quiet_since, last.date())).days
        if quiet_days >= 14:
            weekly.append(f"no activity for {quiet_days} days")
    except Exception:
        pass  # database down or unreadable: skip the activity triggers

    if (now - last).days < FLOOR_DAYS:
        weekly = []
    return urgent, weekly, last


def main(argv):
    now = datetime.datetime.now()
    if "--now" in argv:
        now = datetime.datetime.fromisoformat(argv[argv.index("--now") + 1])
    elif "--today" in argv:
        now = datetime.datetime.fromisoformat(argv[argv.index("--today") + 1] + " 12:00")
    if os.environ.get("JST_DAILY_RUN"):
        return  # the unattended daily run: nobody is there to check in with
    cfg = json.loads((HERE / "checkin.json").read_text())
    if not (PROJECT / ".first_run_done").exists():
        return
    config_dir = PROJECT / cfg["config_dir"]
    read = lambda name: (config_dir / name).read_text() if (config_dir / name).exists() else ""

    def db(sql):
        out = subprocess.run(["psql", "-X", "-q", "-d", cfg["db_name"], "-Atc", sql],
                             capture_output=True, text=True, timeout=5)
        if out.returncode != 0:
            raise RuntimeError(out.stderr)
        return out.stdout.strip()

    urgent, weekly, last = reasons_due(cfg, now, read("reflections.md"), read("criteria.md"), db)
    if urgent or weekly:
        print(f"Check-in due: {'; '.join(urgent + weekly)}. Last check-in: {last:%Y-%m-%d}. "
              "Do what they came for first, then run the search-coach skill's check-in.")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        pass
    sys.exit(0)
