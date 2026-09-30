#!/usr/bin/env python3
"""Postings from Hacker News "Ask HN: Who is hiring?" (public Algolia API, no login).

  hn.py [--month latest|YYYY-MM] [--include ...] [--exclude ...] [--location ...]

Every top-level comment is one posting. Filters apply to the whole comment text.
Comments that name an email address or invite direct contact are flagged
"outreach": true, and their emails are listed, so a short note to a person can
replace a formal application.
"""
import argparse
import html
import json
import re
import sys

import common

API = "https://hn.algolia.com/api/v1"
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
OUTREACH = re.compile(r"email (us|me)|send (us |me )?(your )?(resume|cv)|reach out|no recruiters?|skip the form|contact:", re.I)
HREF = re.compile(r'href="([^"]+)"')


def find_thread(month):
    d = common.get_json(API + "/search_by_date?tags=story,author_whoishiring&hitsPerPage=24")
    hits = [h for h in (d or {}).get("hits", []) if (h.get("title") or "").lower().startswith("ask hn: who is hiring")]
    if month != "latest":
        hits = [h for h in hits if (h.get("created_at") or "").startswith(month)]
    return hits[0] if hits else None


def to_text(raw):
    raw = re.sub(r"(?i)<p>|<br\s*/?>", "\n", raw or "")
    return html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--month", default="latest", help="latest (default) or YYYY-MM")
    common.add_filter_args(ap)
    args = ap.parse_args()
    try:
        thread = find_thread(args.month)
        if not thread:
            common.warn("no 'Who is hiring?' thread found for %s" % args.month)
            sys.exit(3)
        data = common.get_json("%s/items/%s" % (API, thread["objectID"]), timeout=60) or {}
    except common.FetchError as e:
        common.warn("network problem: %s" % e)
        sys.exit(2)
    common.warn("thread: %s (%s), %d top-level comments" % (thread["title"], thread["objectID"], len(data.get("children", []))))
    jobs = []
    for c in data.get("children", []):
        if not c.get("text"):
            continue  # deleted or dead
        text = to_text(c["text"])
        header = text.split("\n", 1)[0]
        parts = [p.strip() for p in header.split("|")]
        company = re.sub(r"\s*https?://\S+", "", parts[0]).strip() or parts[0]
        # Header formats vary; the title is the first later part that is not just a website address.
        titles = [p for p in parts[1:] if p and not re.match(r"^(https?://|www\.)\S+$", p)]
        job = {"source": "hn", "company": html.unescape(company)[:80], "title": titles[0] if titles else header[:100],
               "location": " | ".join(parts[2:4]) if len(parts) > 2 else "", "remote": True if re.search(r"remote", header, re.I) else None,
               "url": "https://news.ycombinator.com/item?id=%s" % c["id"], "posted": c.get("created_at"), "comp": None,
               "header": header[:200], "text": text[:700], "full_text_chars": len(text),
               "emails": sorted(set(EMAIL.findall(text)))[:3],
               "links": [html.unescape(u) for u in HREF.findall(c["text"])][:3]}
        job["outreach"] = bool(job["emails"] or OUTREACH.search(text))
        job["_all_text"] = text
        jobs.append(job)
    kept = []
    for j in jobs:
        if common.keep(dict(j, title=j["_all_text"]), args):
            j.pop("_all_text")
            kept.append(j)
    common.emit_all(kept, args, "hn")


if __name__ == "__main__":
    main()
