#!/usr/bin/env python3
"""Recent startup postings from Y Combinator's public job listing pages (no login).

  yc.py [--role software-engineer,product-manager] [--locations remote,san-francisco]
        [--include ...] [--exclude ...] [--location ...] [--internships]

Each listing page shows only the ~40 newest postings, so coverage comes from
combining roles with locations. This reads a page's embedded JSON, which YC can
change at any time: if that happens the tool says so and exits with code 2
instead of guessing.
"""
import argparse
import concurrent.futures as cf
import html
import json
import re
import sys

import common

BASE = "https://www.ycombinator.com"
ROLES = ["software-engineer", "designer", "product-manager", "recruiting-hr", "sales-manager", "marketing", "support", "operations", "science"]
LOCATIONS = ["remote", "san-francisco", "new-york", "los-angeles", "seattle", "austin", "chicago", "india"]


def fetch_page(path):
    body = common.http_get(BASE + path, timeout=30, browser_ua=True)
    if body is None:
        return path, None, "not found"
    m = re.search(r'data-page="([^"]+)"', body.decode("utf-8", "replace"))
    if not m:
        return path, None, "no embedded data (page format changed?)"
    try:
        return path, json.loads(html.unescape(m.group(1)))["props"]["jobPostings"], None
    except (ValueError, KeyError):
        return path, None, "unexpected data shape (page format changed?)"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--role", default="software-engineer", help="comma-separated: " + ", ".join(ROLES))
    ap.add_argument("--locations", default="remote", help="comma-separated: " + ", ".join(LOCATIONS) + " (also searches with no location)")
    ap.add_argument("--internships", action="store_true", help="include internships (skipped by default)")
    common.add_filter_args(ap)
    args = ap.parse_args()
    roles = [r.strip() for r in args.role.split(",") if r.strip()]
    locs = [x.strip() for x in args.locations.split(",") if x.strip()]
    bad = [r for r in roles if r not in ROLES] + [x for x in locs if x not in LOCATIONS]
    if bad:
        common.warn("unknown value(s): %s\nroles: %s\nlocations: %s" % (", ".join(bad), ", ".join(ROLES), ", ".join(LOCATIONS)))
        sys.exit(2)
    paths = []
    for r in roles:
        paths.append("/jobs/role/" + r)
        paths += ["/jobs/role/%s/%s" % (r, x) for x in locs]
    postings, errors = {}, 0
    try:
        with cf.ThreadPoolExecutor(4) as ex:
            for path, page, err in ex.map(fetch_page, paths):
                if err:
                    errors += 1
                    common.warn("%s: %s" % (path, err))
                    continue
                for p in page:
                    postings[p["id"]] = p
    except common.FetchError as e:
        common.warn("network problem: %s" % e)
        sys.exit(2)
    if errors == len(paths):
        common.warn("YC: every page failed; skipping this source today")
        sys.exit(2)
    common.warn("YC: %d unique postings from %d pages (%d failed)" % (len(postings), len(paths) - errors, errors))
    jobs = []
    for p in postings.values():
        if not args.internships and "intern" in (p.get("type") or "").lower():
            continue
        loc = p.get("location") or ""
        j = {"source": "yc", "company": p.get("companyName"), "title": p.get("title"), "location": loc,
             "remote": True if "remote" in loc.lower() else None, "url": BASE + p["url"], "posted": None,
             "comp": p.get("salaryRange") or None, "type": p.get("type"), "min_experience": p.get("minExperience"),
             "batch": p.get("companyBatchName"), "about": (p.get("companyOneLiner") or "")[:140]}
        if common.keep(j, args):
            jobs.append(j)
    jobs.sort(key=lambda j: (j["company"] or "").lower())
    common.emit_all(jobs, args, "yc")


if __name__ == "__main__":
    main()
