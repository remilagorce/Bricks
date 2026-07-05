#!/usr/bin/env python3
"""Company-news engine — deterministic plumbing for signal-person pass 4.

Google News publishes public RSS feeds: free, no key, stdlib-parseable.
One fetch per company returns dated, sourced articles. This tool fetches
and filters them mechanically; RELEVANCE stays with the calling skill
(homonyms are a judgment call — 'DUPIN' the roofer vs Dupin the senator),
and database writes stay with db-writer. This tool NEVER touches
bricks.db: it only writes staging files.

Used by: signal-person pass 4 (company news).

Usage:
    python3 news.py --companies companies.json --out staging/news-<date> \
        [--days 31] [--terms "levée,acquisition,ouverture"]

companies.json: [{"company_id": 3, "name": "ACME SARL", "location": "33"}]

Output files in --out:
    news.jsonl       dated items per company, freshest first, ≤5/company
    companies.jsonl  per-company verdict: news | quiet (+ warning flag)
    summary.json     counts, errors, spend=0 — receipt material

Every item carries: published date (ISO), outlet, url (Google News link,
resolves to the article), term_hits (offer-relevant vocabulary matched),
warning=true when distress vocabulary matched (redressement, liquidation
— kill-gate material, not an icebreaker), name_in_title.
"""

import argparse
import datetime
import email.utils
import html as htmllib
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
RATE_SLEEP = 0.6
TIMEOUT = 20
TODAY = datetime.date.today()
MAX_PER_COMPANY = 5

DEFAULT_TERMS = ["levée", "levee de fonds", "acquisition", "rachat",
                 "ouverture", "agrandissement", "déménagement", "embauche",
                 "recrute", "croissance", "partenariat", "lauréat", "prix",
                 "contrat", "chantier", "investissement", "anniversaire"]
WARN_TERMS = ["redressement judiciaire", "liquidation", "procédure collective",
              "dépôt de bilan", "plan social", "fermeture"]

state = {"fetches": 0, "errors": []}


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def norm(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def fetch(url):
    for attempt in (1, 2):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = resp.read()
            state["fetches"] += 1
            time.sleep(RATE_SLEEP)
            return data
        except Exception as e:
            if attempt == 2:
                state["errors"].append(f"{url} -> {e}")
                return None
            time.sleep(1.5)


def rss_url(company_name):
    # exact-phrase query; FR edition. Legal-form suffixes water the match
    # down, so they are stripped from the phrase.
    name = re.sub(r"\b(sarl|sas|sasu|eurl|sa|sci)\b\.?", "", company_name,
                  flags=re.I).strip() or company_name
    q = urllib.parse.quote(f'"{name}"')
    return (f"https://news.google.com/rss/search?q={q}"
            f"&hl=fr&gl=FR&ceid=FR:fr")


def parse_items(xml_bytes):
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        state["errors"].append(f"rss parse -> {e}")
        return []
    items = []
    for it in root.iter("item"):
        get = lambda tag: (it.findtext(tag) or "").strip()
        pub = None
        try:
            pub = email.utils.parsedate_to_datetime(get("pubDate")).date()
        except Exception:
            pass
        desc = re.sub(r"<[^>]+>", " ", htmllib.unescape(get("description")))
        items.append({
            "title": htmllib.unescape(get("title")),
            "url": get("link"),
            "outlet": (it.findtext("source") or "").strip(),
            "published": pub.isoformat() if pub else None,
            "_desc": re.sub(r"\s+", " ", desc).strip()[:300],
        })
    return items


def term_hits(text, terms):
    hay = norm(text)
    return sorted({t for t in terms if t and norm(t) in hay})


def run(args):
    rows = json.load(open(args.companies, encoding="utf-8"))
    terms = [t.strip() for t in args.terms.split(",") if t.strip()] \
        if args.terms else DEFAULT_TERMS
    cutoff = TODAY - datetime.timedelta(days=args.days)
    all_items, verdicts, dropped_old = [], [], 0

    for c in rows:
        name = c.get("name", "")
        log(f"[news] {name}")
        xml_bytes = fetch(rss_url(name))
        items = parse_items(xml_bytes) if xml_bytes else []
        kept = []
        for it in items:
            if not it["published"] or it["published"] < cutoff.isoformat():
                dropped_old += 1
                continue
            blob = it["title"] + " " + it["_desc"]
            it.pop("_desc")
            it["company_id"] = c.get("company_id")
            it["company_name"] = name
            it["age_days"] = (TODAY - datetime.date.fromisoformat(
                it["published"])).days
            it["term_hits"] = term_hits(blob, terms)
            it["warning"] = bool(term_hits(blob, WARN_TERMS))
            it["name_in_title"] = norm(name) in norm(it["title"]) or any(
                tok in norm(it["title"]).split()
                for tok in norm(name).split() if len(tok) > 3)
            kept.append(it)
        kept.sort(key=lambda i: i["published"], reverse=True)
        kept = kept[:MAX_PER_COMPANY]
        all_items += kept
        verdicts.append({
            "company_id": c.get("company_id"), "company_name": name,
            "found": len(kept),
            "freshest": kept[0]["published"] if kept else None,
            "verdict": "news" if kept else "quiet",
            "warning": any(i["warning"] for i in kept),
        })

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "news.jsonl", "w", encoding="utf-8") as f:
        for it in all_items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    with open(out / "companies.jsonl", "w", encoding="utf-8") as f:
        for v in verdicts:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")
    summary = {
        "mode": "news", "companies_checked": len(rows),
        "with_news": sum(1 for v in verdicts if v["verdict"] == "news"),
        "quiet": sum(1 for v in verdicts if v["verdict"] == "quiet"),
        "items": len(all_items), "dropped_older_than_window": dropped_old,
        "window_days": args.days, "warnings": sum(
            1 for v in verdicts if v["warning"]),
        "spend_credits": 0, "fetches": state["fetches"],
        "errors": state["errors"][:20],
    }
    with open(out / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description="Company-news engine (Google News RSS)")
    p.add_argument("--companies", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--days", type=int, default=31)
    p.add_argument("--terms", default="",
                   help="comma-separated offer-relevant vocabulary "
                        "(default: built-in French GTM terms)")
    run(p.parse_args())


if __name__ == "__main__":
    main()
