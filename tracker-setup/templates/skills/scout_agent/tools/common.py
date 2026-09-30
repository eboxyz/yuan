"""Shared helpers for the scout tools. Standard library only (Python 3.9+).

These tools only ever make plain GET requests to public pages and APIs. They
never log in, submit anything, or create accounts. Output is JSON lines on
stdout; notes and errors go to stderr.
"""
import json
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parents[3]  # <project>/.claude/skills/<skill>/tools -> <project>
UA = "yuan-scout/1.0 (+https://github.com/eboxyz/yuan)"
MIN_INTERVAL = 0.15  # seconds between requests, across threads

_lock = threading.Lock()
_last = [0.0]


def load_config():
    with open(TOOLS_DIR / "tools.json") as f:
        return json.load(f)


CFG = load_config()


def config_path(name):
    return ROOT / CFG["config_dir"] / name


def warn(msg):
    print(msg, file=sys.stderr)


class FetchError(Exception):
    pass


def http_get(url, timeout=25, browser_ua=False):
    """Return the response body as bytes, or None on a 404. Raises FetchError otherwise."""
    with _lock:
        wait = MIN_INTERVAL - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
    headers = {"User-Agent": "Mozilla/5.0" if browser_ua else UA, "Accept": "*/*"}
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise FetchError("HTTP %s for %s" % (e.code, url))
    except (urllib.error.URLError, OSError) as e:
        raise FetchError("%s for %s" % (e, url))


def get_json(url, timeout=25):
    body = http_get(url, timeout=timeout)
    return None if body is None else json.loads(body.decode("utf-8", "replace"))


def norm_url(u):
    return (u or "").split("#")[0].split("?")[0].rstrip("/")


def reviewed_urls():
    path = config_path("reviewed_postings.jsonl")
    out = set()
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                u = json.loads(line).get("url")
            except ValueError:
                continue
            if u:
                out.add(norm_url(u))
    return out


def tracked_companies():
    """Names already in the tracker (lowercased). Fails soft: warns and returns an empty set."""
    sql = "select %s from %s" % (CFG["primary_field"], CFG["entity_plural"])
    try:
        out = subprocess.check_output(
            ["psql", "-d", CFG["db_name"], "-Atc", sql], stderr=subprocess.STDOUT, timeout=15
        ).decode()
        return {ln.strip().lower() for ln in out.splitlines() if ln.strip()}
    except Exception as e:  # psql missing, db down, etc.
        warn("note: could not read the tracker (%s); not hiding companies you already track" % e.__class__.__name__)
        return set()


def add_filter_args(parser):
    parser.add_argument("--include", default="", help="comma-separated words/phrases; keep results matching ANY (all words of a phrase must appear)")
    parser.add_argument("--exclude", default="", help="comma-separated words/phrases; drop results matching ANY")
    parser.add_argument("--location", default="", help="comma-separated substrings; keep results whose location matches ANY ('remote' also matches remote roles)")
    parser.add_argument("--limit", type=int, default=100, help="max results to print (default 100)")
    parser.add_argument("--all", action="store_true", help="also show postings you already reviewed and companies you already track")


def _phrases(csv):
    return [p.split() for p in (x.strip().lower() for x in csv.split(",")) if p]


def _has(text, phrases):
    t = text.lower()
    return any(all(w in t for w in ph) for ph in phrases)


def keep(job, args, text_key="title"):
    """Apply --include / --exclude / --location to one normalized job."""
    text = job.get(text_key) or ""
    inc, exc = _phrases(args.include), _phrases(args.exclude)
    if inc and not _has(text, inc):
        return False
    if exc and _has(text, exc):
        return False
    locs = [x.strip().lower() for x in args.location.split(",") if x.strip()]
    if locs:
        loc = (job.get("location") or "").lower()
        remote_ok = "remote" in locs and (job.get("remote") is True or "remote" in loc)
        if not remote_ok and not any(x in loc for x in locs):
            return False
    return True


def emit_all(jobs, args, source):
    """Hide already-reviewed / already-tracked results (unless --all), print JSON lines, report counts."""
    reviewed = reviewed_urls()
    tracked = tracked_companies()
    shown = hidden_reviewed = hidden_tracked = 0
    for j in jobs:
        is_reviewed = norm_url(j.get("url")) in reviewed
        is_tracked = (j.get("company") or "").strip().lower() in tracked
        j["reviewed"], j["tracked"] = is_reviewed, is_tracked
        if not args.all:
            if is_reviewed:
                hidden_reviewed += 1
                continue
            if is_tracked:
                hidden_tracked += 1
                continue
        if shown >= args.limit:
            break
        print(json.dumps(j, ensure_ascii=False))
        shown += 1
    warn("%s: printed %d; hid %d already reviewed and %d at companies you track" % (source, shown, hidden_reviewed, hidden_tracked))
