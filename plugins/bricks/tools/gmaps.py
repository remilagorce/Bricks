#!/usr/bin/env python3
"""Google Maps discovery — deterministic plumbing for find-gmaps.

Bright Data's Google Maps dataset (`discover_new` by location) turns one
or more Maps queries ("courtier assurance lyon") into place records. This
tool submits the queries, polls the snapshot until ready, extracts every
VERIFIED website domain, writes them to a PROVISIONAL CSV, then prints
that file IN FULL on stdout. It NEVER touches bricks.db: the calling
skill imports the CSV via `db.py import-csv --key domain`, then deletes
it (CONVENTIONS §5, §6 — the database is the checkpoint, not the file).

Used by: find-gmaps.

Usage:
    python3 gmaps.py --queries "courtier assurance lyon" "courtier assurance paris" \
        --out <ws>/staging/find-gmaps-<date>/domains.csv [--country FR] [--limit 50]
    python3 gmaps.py --keyword "courtier assurance" --locations "lyon, paris" \
        --out ... [--limit 50]
    python3 gmaps.py --snapshot s_xxxxx --out ...     # resume: fetch a PAID snapshot

Money notes (CONVENTIONS §8): every record returned is METERED by Bright
Data — cap the spend with --limit (records per query). The snapshot_id is
printed on stderr as soon as the job is submitted; an interrupted run
resumes with --snapshot instead of submitting (and paying) twice — the
calling skill stores it in memory/state.json.

Output CSV columns: name, domain, phone, address, category, rating,
reviews_count, query, source, status — deduped on domain, rows without a
usable company domain are dropped (counted in the receipt). stdout gets
the whole file (--no-print disables); stderr gets progress lines and a
final one-line JSON receipt (counts, snapshot_id, elapsed_s).

Env: BRIGHTDATA_API_TOKEN (self-loaded from ~/.bricks/env via envfile).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envfile  # noqa: E402

envfile.load()  # ~/.bricks/env → BRIGHTDATA_API_TOKEN without shell exports

DATASET_ID = "gd_m8ebnr0q2qlklc02fz"  # Bright Data "Google Maps places"
SCRAPE_URL = ("https://api.brightdata.com/datasets/v3/scrape"
              f"?dataset_id={DATASET_ID}"
              "&notify=false&include_errors=true"
              "&type=discover_new&discover_by=location")
SNAPSHOT_URL = ("https://api.brightdata.com/datasets/v3/snapshot/"
                "{snapshot_id}?format=json")
TIMEOUT = 60          # per HTTP call
POLL_INTERVAL = 15    # seconds between snapshot polls
MAX_WAIT = 1800       # give up polling after 30 min (snapshot stays fetchable)

#: Link-in-bio / social / booking platforms — a place whose "website" lives
#: there has NO company domain; the row is dropped and counted, never guessed.
PLATFORM_HOSTS = {
    "google.com", "facebook.com", "instagram.com", "linkedin.com",
    "twitter.com", "x.com", "youtube.com", "tiktok.com", "wa.me",
    "whatsapp.com", "calendly.com", "linktr.ee", "pagesjaunes.fr",
    "booking.com", "tripadvisor.com", "tripadvisor.fr", "doctolib.fr",
}

CSV_COLUMNS = ["name", "domain", "phone", "address", "category",
               "rating", "reviews_count", "query", "source", "status"]

CSV_QUOTING = dict(quoting=csv.QUOTE_MINIMAL, lineterminator="\n")


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def api_call(url: str, token: str, body: dict | None = None) -> tuple[int, bytes]:
    """One HTTP call; returns (status, raw body). 202 is a value, not an error."""
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "bricks-gmaps"},
        method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 202:  # snapshot still building — a state, not a failure
            return 202, b""
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"HTTP {exc.code} on {url.split('?')[0]}: {detail}")


def submit(queries: list[str], country: str, limit: int | None,
           token: str) -> str:
    payload: dict = {"input": [{"keyword": q, "country": country}
                               for q in queries]}
    if limit is not None:
        payload["limit_per_input"] = limit
    status, raw = api_call(SCRAPE_URL, token, body=payload)
    data = json.loads(raw)
    snapshot_id = data.get("snapshot_id")
    if not snapshot_id:
        raise RuntimeError(f"no snapshot_id in submit response: {data}")
    return snapshot_id


def poll_snapshot(snapshot_id: str, token: str) -> list[dict]:
    url = SNAPSHOT_URL.format(snapshot_id=snapshot_id)
    deadline = time.monotonic() + MAX_WAIT
    while True:
        status, raw = api_call(url, token)
        if status == 200:
            data = json.loads(raw)
            if isinstance(data, dict):  # error/status object, not records
                raise RuntimeError(f"snapshot answered an object: {data}")
            return data
        if time.monotonic() > deadline:
            raise RuntimeError(
                f"snapshot {snapshot_id} not ready after {MAX_WAIT}s — "
                f"resume later with --snapshot {snapshot_id} (already paid)")
        log(f"  snapshot en cours... (retry dans {POLL_INTERVAL}s)")
        time.sleep(POLL_INTERVAL)


def website_of(place: dict) -> str:
    """The place's website URL — open_website, else the 'authority' link."""
    url = (place.get("open_website") or "").strip()
    if url:
        return url
    for detail in place.get("business_details") or []:
        if detail.get("field_name") == "authority" and detail.get("link"):
            return detail["link"].strip()
    return ""


def domain_of(url: str) -> str:
    """Bare host (www. stripped) — empty when it's a platform, not a site."""
    if url and "://" not in url:
        url = "http://" + url
    host = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    if not host or "." not in host:
        return ""
    if any(host == p or host.endswith("." + p) for p in PLATFORM_HOSTS):
        return ""
    return host


def to_rows(records: list[dict]) -> tuple[list[dict], dict]:
    """Records → CSV rows deduped on domain, + drop counters for the receipt."""
    rows: list[dict] = []
    seen: set[str] = set()
    dropped = {"closed": 0, "no_site": 0, "platform_site": 0, "duplicate": 0}
    for place in records:
        if place.get("permanently_closed"):
            dropped["closed"] += 1
            continue
        url = website_of(place)
        if not url:
            dropped["no_site"] += 1
            continue
        domain = domain_of(url)
        if not domain:
            dropped["platform_site"] += 1
            continue
        if domain in seen:
            dropped["duplicate"] += 1
            continue
        seen.add(domain)
        rows.append({
            "name": (place.get("name") or "").strip(),
            "domain": domain,
            "phone": (place.get("phone_number") or "").strip(),
            "address": (place.get("address") or "").strip(),
            "category": (place.get("category") or "").strip(),
            "rating": place.get("rating") or "",
            "reviews_count": place.get("reviews_count") or "",
            # discover_new echoes the submitted query in discovery_input
            "query": (place.get("discovery_input") or {}).get("keyword") or "",
            "source": "gmaps",
            "status": "new",
        })
    return rows, dropped


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Google Maps → domains CSV via Bright Data (find-gmaps)")
    parser.add_argument("--queries", nargs="+", metavar="QUERY",
                        help='full Maps queries: "courtier assurance lyon" ...')
    parser.add_argument("--keyword",
                        help="keyword crossed with --locations")
    parser.add_argument("--locations",
                        help='comma-separated locations: "lyon, paris, nice"')
    parser.add_argument("--snapshot", metavar="SNAPSHOT_ID",
                        help="fetch an ALREADY-PAID snapshot instead of submitting")
    parser.add_argument("--country", default="FR")
    parser.add_argument("--limit", type=int, default=None, metavar="N",
                        help="max records per query — THE spend cap (§8)")
    parser.add_argument("--out", required=True, metavar="FILE.csv",
                        help="provisional CSV path (workspace staging/)")
    parser.add_argument("--no-print", action="store_true",
                        help="skip printing the whole CSV on stdout")
    args = parser.parse_args()

    queries: list[str] = []
    if args.queries:
        queries = args.queries
    elif args.keyword and args.locations:
        locations = [l.strip() for l in args.locations.split(",") if l.strip()]
        queries = [f"{args.keyword} {loc}" for loc in locations]
    if not queries and not args.snapshot:
        parser.error("provide --queries, --keyword + --locations, or --snapshot")

    token = os.environ.get("BRIGHTDATA_API_TOKEN", "").strip()
    if not token:
        print(json.dumps({"ok": False, "error":
                          "BRIGHTDATA_API_TOKEN absent de l'environnement "
                          "(envfile.py set BRIGHTDATA_API_TOKEN <token>)"}),
              file=sys.stderr)
        sys.exit(1)

    t0 = time.monotonic()
    try:
        if args.snapshot:
            snapshot_id = args.snapshot
            log(f"Reprise du snapshot {snapshot_id} (déjà payé)...")
        else:
            log(f"Soumission de {len(queries)} requête(s) Google Maps...")
            for q in queries:
                log(f"  - {q}")
            snapshot_id = submit(queries, args.country, args.limit, token)
            # printed FIRST so an interrupted run can resume without repaying
            log(f"snapshot_id: {snapshot_id}")
        records = poll_snapshot(snapshot_id, token)
    except (RuntimeError, urllib.error.URLError, OSError,
            json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        sys.exit(1)

    rows, dropped = to_rows(records)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, **CSV_QUOTING)
        writer.writeheader()
        writer.writerows(rows)

    if not args.no_print:
        with open(args.out, encoding="utf-8") as f:
            sys.stdout.write(f.read())
        sys.stdout.flush()

    receipt = {"ok": True, "action": "gmaps", "snapshot_id": snapshot_id,
               "queries": len(queries), "places": len(records),
               "domains": len(rows), "dropped": dropped, "csv": args.out,
               "elapsed_s": round(time.monotonic() - t0, 1)}
    print(json.dumps(receipt, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
