#!/usr/bin/env python3
"""Open roles from company job boards on Greenhouse and Ashby (public APIs, no login).

  boards.py lookup "Company" ["Other Co" ...]   find and cache each company's board
  boards.py jobs "Company" [filters]            open roles at one company
  boards.py sweep [filters]                     every cached board plus watch_companies.txt
  boards.py describe --ats A --slug S --id ID   full text of one posting

Lookups are cached in known_boards.json. A miss is recorded with the names that
were tried, and is not re-probed for 30 days (use --refresh to force).
"""
import argparse
import concurrent.futures as cf
import datetime
import html
import json
import re
import sys

import common

CACHE_DAYS = 30
SUFFIXES = {"inc", "llc", "ltd", "corp", "co", "corporation", "company", "the"}


def cache_path():
    return common.config_path("known_boards.json")


def load_cache():
    p = cache_path()
    if p.exists():
        try:
            return json.loads(p.read_text() or "{}")
        except ValueError:
            common.warn("known_boards.json is not valid JSON; starting a fresh cache in memory")
    return {}


def save_cache(cache):
    cache_path().write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n")


def key_of(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def slug_candidates(name):
    words = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if w not in SUFFIXES]
    if not words:
        return []
    joined, hyphen = "".join(words), "-".join(words)
    cands = [joined, hyphen, joined + "hq", "get" + joined, joined + "inc"]
    if len(words) > 1:
        cands.append(words[0])
    seen, out = set(), []
    for c in cands:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def names_match(a, b):
    a, b = key_of(a), key_of(b)
    return bool(a and b) and (a == b or (min(len(a), len(b)) >= 4 and (a in b or b in a)))


def gh_board_name(slug):
    d = common.get_json("https://boards-api.greenhouse.io/v1/boards/%s" % slug)
    return None if d is None else d.get("name")


def ashby_exists(slug):
    d = common.get_json("https://api.ashbyhq.com/posting-api/job-board/%s" % slug)
    return d is not None and isinstance(d.get("jobs"), list)


def lookup(name, cache, refresh=False):
    key = key_of(name)
    hit = cache.get(key)
    if hit and not refresh:
        if hit.get("ats"):
            return dict(hit, source="cache")
        checked = datetime.date.fromisoformat(hit["checked"])
        if (datetime.date.today() - checked).days < CACHE_DAYS:
            return dict(hit, source="cache", note="cached miss; re-probes after %d days" % CACHE_DAYS)
    tried = []
    today = datetime.date.today().isoformat()
    full_name_slugs = set(slug_candidates(name)[:2])  # joined and hyphenated, legal suffixes removed
    for slug in slug_candidates(name):
        try:
            board = gh_board_name(slug)
        except common.FetchError as e:
            tried.append("greenhouse:%s (error: %s)" % (slug, e))
            board = None
        if board is not None:
            if names_match(board, name):
                res = {"company": name, "ats": "greenhouse", "slug": slug, "verified": True, "board_name": board, "found": today}
                cache[key] = res
                return dict(res, source="lookup")
            tried.append("greenhouse:%s (a board exists but it is named %r, not %r)" % (slug, board, name))
        else:
            tried.append("greenhouse:%s" % slug)
        # Ashby returns no company name, so only accept the full-name slugs, and say it is unverified.
        if slug in full_name_slugs:
            try:
                if ashby_exists(slug):
                    res = {"company": name, "ats": "ashby", "slug": slug, "verified": False,
                           "note": "Ashby gives no company name: confirm one job URL really is this company", "found": today}
                    cache[key] = res
                    return dict(res, source="lookup")
            except common.FetchError as e:
                tried.append("ashby:%s (error: %s)" % (slug, e))
            tried.append("ashby:%s" % slug)
    res = {"company": name, "ats": None, "miss": True, "tried": tried, "checked": today}
    cache[key] = res
    return dict(res, source="lookup")


def strip_html(s):
    # Greenhouse sends its description entity-encoded, so decode first, strip tags, then decode what is left.
    s = html.unescape(s or "")
    s = re.sub(r"(?i)<\s*(br|/p|/li|/h[1-6])\s*/?>", "\n", s)
    s = re.sub(r"(?i)<li[^>]*>", "- ", s)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def fetch_jobs(entry):
    ats, slug, company = entry["ats"], entry["slug"], entry.get("board_name") or entry["company"]
    out = []
    if ats == "greenhouse":
        d = common.get_json("https://boards-api.greenhouse.io/v1/boards/%s/jobs" % slug) or {}
        for j in d.get("jobs", []):
            loc = (j.get("location") or {}).get("name") or ""
            out.append({"source": "greenhouse", "company": company, "title": j.get("title"), "location": loc,
                        "remote": True if "remote" in loc.lower() else None, "url": j.get("absolute_url"),
                        "posted": j.get("first_published") or j.get("updated_at"), "comp": None,
                        "ref": {"ats": "greenhouse", "slug": slug, "id": str(j.get("id"))}})
    elif ats == "ashby":
        d = common.get_json("https://api.ashbyhq.com/posting-api/job-board/%s?includeCompensation=true" % slug) or {}
        for j in d.get("jobs", []):
            if j.get("isListed") is False:
                continue
            c = j.get("compensation") or {}
            # Ashby's isRemote is also true for hybrid roles, so trust workplaceType when it is present.
            wt = j.get("workplaceType")
            remote = (wt == "Remote") if wt else j.get("isRemote")
            out.append({"source": "ashby", "company": company, "title": j.get("title"), "location": j.get("location") or "",
                        "remote": remote, "workplace": wt, "url": j.get("jobUrl"), "posted": j.get("publishedAt"),
                        "comp": c.get("compensationTierSummary") or c.get("scrapeableCompensationSalarySummary"),
                        "department": j.get("department"), "team": j.get("team"),
                        "ref": {"ats": "ashby", "slug": slug, "id": j.get("id")}})
    return out


def watch_companies():
    p = common.config_path("watch_companies.txt")
    if not p.exists():
        return []
    return [ln.strip() for ln in p.read_text().splitlines() if ln.strip() and not ln.strip().startswith("#")]


def cmd_lookup(args):
    cache = load_cache()
    for name in args.companies:
        print(json.dumps(lookup(name, cache, args.refresh), ensure_ascii=False))
    save_cache(cache)


def cmd_jobs(args):
    cache = load_cache()
    res = lookup(args.company, cache, args.refresh)
    save_cache(cache)
    if not res.get("ats"):
        print(json.dumps(res, ensure_ascii=False))
        common.warn("no board found for %r; tried: %s" % (args.company, "; ".join(res.get("tried", []))))
        return 3
    jobs = [j for j in fetch_jobs(res) if common.keep(j, args)]
    common.emit_all(jobs, args, "%s/%s" % (res["ats"], res["slug"]))


def cmd_sweep(args):
    cache = load_cache()
    entries = {k: v for k, v in cache.items() if v.get("ats")}
    for name in watch_companies():
        res = lookup(name, cache, args.refresh)
        if res.get("ats"):
            entries[key_of(name)] = res
        else:
            common.warn("watch company %r: no board found (tried %d names)" % (name, len(res.get("tried", []))))
    save_cache(cache)
    if not entries:
        common.warn("no known boards yet: add companies to watch_companies.txt or run `boards.py lookup \"Company\"` first")
        return 3
    jobs, failures = [], 0

    def one(entry):
        try:
            return entry, fetch_jobs(entry), None
        except Exception as e:
            return entry, [], e

    with cf.ThreadPoolExecutor(4) as ex:
        for entry, found, err in ex.map(one, list(entries.values())):
            if err:
                failures += 1
                common.warn("%s/%s failed: %s" % (entry["ats"], entry["slug"], err))
            jobs += [j for j in found if common.keep(j, args)]
    jobs.sort(key=lambda j: j.get("posted") or "", reverse=True)
    common.warn("swept %d boards (%d failed)" % (len(entries), failures))
    common.emit_all(jobs, args, "sweep")


def cmd_describe(args):
    if args.ats == "greenhouse":
        d = common.get_json("https://boards-api.greenhouse.io/v1/boards/%s/jobs/%s" % (args.slug, args.id))
        if d is None:
            common.warn("posting not found (it may have been taken down)")
            return 3
        print(d.get("title", ""), "\n", d.get("location", {}).get("name", ""), "\n\n", strip_html(d.get("content")))
    elif args.ats == "ashby":
        d = common.get_json("https://api.ashbyhq.com/posting-api/job-board/%s?includeCompensation=true" % args.slug) or {}
        for j in d.get("jobs", []):
            if j.get("id") == args.id:
                print(j.get("title", ""), "\n", j.get("location", ""), "\n\n", j.get("descriptionPlain") or strip_html(j.get("descriptionHtml")))
                return
        common.warn("posting not found (it may have been taken down)")
        return 3
    else:
        common.warn("--ats must be greenhouse or ashby")
        return 2


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("lookup")
    p.add_argument("companies", nargs="+")
    p.add_argument("--refresh", action="store_true")
    p.set_defaults(fn=cmd_lookup)
    p = sub.add_parser("jobs")
    p.add_argument("company")
    p.add_argument("--refresh", action="store_true")
    common.add_filter_args(p)
    p.set_defaults(fn=cmd_jobs)
    p = sub.add_parser("sweep")
    p.add_argument("--refresh", action="store_true")
    common.add_filter_args(p)
    p.set_defaults(fn=cmd_sweep)
    p = sub.add_parser("describe")
    p.add_argument("--ats", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--id", required=True)
    p.set_defaults(fn=cmd_describe)
    args = ap.parse_args()
    try:
        sys.exit(args.fn(args) or 0)
    except common.FetchError as e:
        common.warn("network problem: %s" % e)
        sys.exit(2)


if __name__ == "__main__":
    main()
