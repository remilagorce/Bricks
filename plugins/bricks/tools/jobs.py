#!/usr/bin/env python3
"""Hiring-signal hunt engine — deterministic plumbing for the hiring bricks.

Fetches FREE public job sources in plain Python, politely: France Travail
keyword-search pages (+ offer detail microdata), HelloWork search pages,
company career pages. No LLM in the loop: this tool generates queries from
a confirmed pain matrix, parses structured offer cards, flags agency and
stage noise, matches tool/pain keywords and pre-scores the mechanical part
of the grid (max 65/100). Judgment — category fit, angles, the final cut —
stays with the calling skill; database writes go through db.py. This
tool NEVER touches bricks.db: it only writes staging files.

Used by: find-hiring-signal (hunt mode), signal-person pass 3 (check mode).

Usage:
    python3 jobs.py hunt --matrix matrix.json --out staging/hiring-<date>
    python3 jobs.py check --companies companies.json --out staging/signals-<date> \
        --keywords "couvreur,charpentier"   # trade sweep shared by the batch
    options: --max-queries 30  --max-details 40  --keep-agencies  --workers 6

Fetches run in parallel (--workers) behind a PER-HOST rate limiter:
request starts on one host stay RATE_SLEEP apart (politeness unchanged),
different hosts proceed concurrently. Output files are identical to the
serial version — results are assembled in input order.

matrix.json (hunt):
    {"titles": ["couvreur", ...],             REQUIRED - one query per title x location
     "locations": ["33", "69R", "Bordeaux"],  dept number, FT region code, or city
                                              (legacy "<dept>D" accepted, auto-stripped: dead endpoint)
     "tools": ["PRODEVIS", ...],              matched in descriptions, never queried
     "pains": ["surcroit", ...],              matched in descriptions, never queried
     "negative": ["..."],                     extra agency brands to flag
     "sources": ["francetravail", "hellowork"]}

companies.json (check):
    [{"company_id": 3, "name": "...", "domain": "acme.fr", "location": "33"}]

Output files in --out:
    offers.jsonl     kept offers, prescore-sorted, one JSON per line
    rejected.jsonl   agency / stage / expired / anonymous rows, with reason
    companies.jsonl  per-company aggregation (volume, freshest, prescore)
    summary.json     counts, caps, errors, spend=0 — the receipt material
"""

import argparse
import concurrent.futures
import datetime
import html as htmllib
import json
import re
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
RATE_SLEEP = 0.8
TIMEOUT = 20
TODAY = datetime.date.today()

AGENCY_TOKENS = [
    "interim", "intérim", "agence d'emploi", "travail temporaire",
    "cabinet de recrutement", "recrute pour",  # the "X recrute pour X" formula
    "adecco", "manpower", "randstad", "aquila rh", "actual", "synergie",
    "crit", "temporis", "proman", "start people", "supplay", "partnaire",
    "welljob", "interaction", "menway", "vitalis", "triangle", "iziwork",
    "gojob", "domino rh", "abalone", "morgan services", "lip", "adequat",
    "happy job", "jubil", "ergalis", "solano", "optineris", "atrihom",
    "advance emploi", "samsic emploi", "job&box", "sovitrat", "up skills",
    "expectra", "hays", "page personnel", "leader", "get carrieres",
    "tt",  # 'TRIDENT TT' — travail-temporaire suffix, word-boundary safe
    # Executive/finance recruiting firms that slipped through a field run
    # (2026-07: Michael Page, LHH, Comptalents, Cliff Partners reached the
    # judgment pass) + their frequent siblings on finance searches:
    "michael page", "pagegroup", "lhh", "comptalents", "cliff partners",
    "robert half", "fed finance", "robert walters", "walters people",
    "fyte", "grant alexander", "harry hope", "winsearch",
]
STAGE_RE = re.compile(r"\b(stage|stagiaire|alternan\w*|apprenti\w*)\b", re.I)
CONTRACT_RE = re.compile(
    r"\b(CDI|CDD|Mission intérimaire|Intérim|Saisonnier|Franchise)\b", re.I)

FR_MONTHS = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
             "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
             "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
             "decembre": 12}

CAREER_PATHS = ["recrutement", "recrutements", "carrieres", "carriere",
                "nous-rejoindre", "rejoignez-nous", "offres-emploi",
                "offre-emploi", "emploi", "jobs", "on-recrute"]
HIRING_WORDS = re.compile(
    r"(recrut\w+|rejoign\w+|embauch\w+|poste[s]? [àa] pourvoir|"
    r"offre[s]? d'emploi|candidature)", re.I)

state = {"fetches": 0, "errors": [], "t0": None}
_state_lock = threading.Lock()


class HostLimiter:
    """Politeness, per host: request starts on ONE host stay `interval`
    apart process-wide; different hosts proceed in parallel."""

    def __init__(self, interval):
        self.interval = interval
        self._lock = threading.Lock()
        self._next_at = {}

    def acquire(self, url):
        host = urllib.parse.urlsplit(url).netloc
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next_at.get(host, 0.0))
            self._next_at[host] = start + self.interval
        if start > now:
            time.sleep(start - now)


LIMITER = HostLimiter(RATE_SLEEP)


def pmap(fn, jobs, workers):
    """Run fn(*args) over a list of args-tuples in parallel; results come
    back in INPUT order, so downstream files stay deterministic."""
    if workers <= 1 or len(jobs) <= 1:
        return [fn(*j) for j in jobs]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fn, *j) for j in jobs]
        return [f.result() for f in futures]


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def fetch(url, binary=False):
    """One polite GET with a single retry; failures land in summary.errors."""
    for attempt in (1, 2):
        try:
            LIMITER.acquire(url)  # all pacing lives here — callers never sleep
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = resp.read()
            with _state_lock:
                state["fetches"] += 1
            return data if binary else data.decode("utf-8", errors="replace")
        except Exception as e:
            if attempt == 2:
                with _state_lock:
                    state["errors"].append(f"{url} -> {e}")
                return None
            time.sleep(1.5)


def norm(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def parse_date(raw):
    """ISO date, French '03 juillet 2026', or 'il y a N jours' -> ISO string."""
    if not raw:
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return m.group(0)
    m = re.search(r"(\d{1,2})(?:er)?\s+([a-zéûôè]+)\s+(\d{4})", raw, re.I)
    if m and norm(m.group(2)) in {norm(k): v for k, v in FR_MONTHS.items()}:
        month = FR_MONTHS[[k for k in FR_MONTHS if norm(k) == norm(m.group(2))][0]]
        return f"{int(m.group(3)):04d}-{month:02d}-{int(m.group(1)):02d}"
    m = re.search(r"il y a\s+(\d+)\s+jour", raw, re.I)
    if m:
        return (TODAY - datetime.timedelta(days=int(m.group(1)))).isoformat()
    if re.search(r"aujourd", raw, re.I):
        return TODAY.isoformat()
    if re.search(r"\bhier\b", raw, re.I):
        return (TODAY - datetime.timedelta(days=1)).isoformat()
    return None


def recency_days(posted):
    if not posted:
        return None
    try:
        return (TODAY - datetime.date.fromisoformat(posted[:10])).days
    except ValueError:
        return None


def keyword_hits(text, keywords):
    hay = norm(text)
    return sorted({k for k in keywords if k and norm(k) in hay})


def agency_suspect(company, title, extra_negative):
    """Word-boundary match only — 'crit' must not fire inside 'électricité'."""
    hay = " " + norm(company + " " + title) + " "
    for token in AGENCY_TOKENS + [n for n in extra_negative if n]:
        t = norm(token)
        if t and f" {t} " in hay:
            return token.strip()
    return None


# ---------------------------------------------------------------- France Travail

def ft_location_code(loc):
    loc = (loc or "").strip()
    # The historic "<dept>D" département code is DEAD: it now 301s to a
    # pretty URL that answers 410 (field-tested 2026-07: whole "chef
    # comptable" sweeps returned 410). The bare dept number is what the
    # search endpoint accepts today (verified live: 200 + offer cards).
    if re.fullmatch(r"\d{2,3}", loc):
        return loc
    if re.fullmatch(r"\d{2,3}D", loc):
        return loc[:-1]  # strip the dead suffix from caller-supplied codes
    if re.fullmatch(r"\d{1,3}R|\d{5}", loc):
        return loc
    return None  # free-text city: goes into motsCles instead


def ft_search(title, location):
    params = {"motsCles": title, "rayon": 10}
    code = ft_location_code(location)
    if code:
        params["lieux"] = code
    elif location:
        params["motsCles"] = f"{title} {location}"
    url = ("https://candidat.francetravail.fr/offres/recherche?"
           + urllib.parse.urlencode(params))
    html = fetch(url)
    if not html:
        return []
    cards = []
    for block in re.split(r'<li data-id-offre="', html)[1:]:
        offer_id = block[:block.find('"')]
        title_m = re.search(
            r'<span class="media-heading-title">(.*?)</span>', block, re.S)
        sub_m = re.search(
            r'<p translate="no" class="subtext">(.*?)</p>', block, re.S)
        desc_m = re.search(r'<p class="description">(.*?)</p>', block, re.S)
        company, location_txt = "", ""
        if sub_m:
            sub = re.sub(r"<[^>]+>", "|", htmllib.unescape(sub_m.group(1)))
            parts = [p.strip(" \xa0-\n") for p in sub.split("|") if p.strip(" \xa0-\n")]
            if parts:
                if re.match(r"\d{2,3} - ", parts[-1]):
                    location_txt = parts[-1]
                    company = " ".join(parts[:-1])
                else:
                    company = " ".join(parts)
        cards.append({
            "source": "francetravail", "offer_id": offer_id,
            "url": f"https://candidat.francetravail.fr/offres/recherche/detail/{offer_id}",
            "title": htmllib.unescape(title_m.group(1)).strip() if title_m else "",
            "company_name": company.strip(),
            "location": location_txt,
            "description": re.sub(r"\s+", " ", htmllib.unescape(
                desc_m.group(1))).strip()[:600] if desc_m else "",
            "posted_date": None, "contract_type": None,
        })
    return cards


def ft_detail(offer):
    """Detail page microdata: date, employer, expiry, contract, full text."""
    html = fetch(offer["url"])
    if not html:
        return offer
    for field, prop in [("posted_date", "datePosted"), ("valid_through", "validThrough")]:
        m = re.search(r'content="([\d-]+)"[^>]*itemprop="%s"' % prop, html) or \
            re.search(r'itemprop="%s"[^>]*content="([\d-]+)"' % prop, html)
        if m:
            offer[field] = m.group(1)
    m = re.search(r'itemprop="hiringOrganization".*?content="([^"]*)"\s*itemprop="name"',
                  html, re.S)
    if m and m.group(1).strip():
        offer["company_name"] = htmllib.unescape(m.group(1)).strip()
    m = re.search(r'itemprop="description"[^>]*>(.*?)</div>', html, re.S)
    if m:
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ",
                      htmllib.unescape(m.group(1)))).strip()
        if len(text) > len(offer.get("description", "")):
            offer["description"] = text[:800]
    m = CONTRACT_RE.search(html)
    if m:
        offer["contract_type"] = m.group(1)
    return offer


# ---------------------------------------------------------------- HelloWork

def hw_search(title, location):
    url = ("https://www.hellowork.com/fr-fr/emploi/recherche.html?"
           + urllib.parse.urlencode({"k": title, "l": location or "France"}))
    html = fetch(url)
    if not html:
        return []
    cards, seen = [], set()
    for m in re.finditer(
            r'href="/fr-fr/emplois/(\d+)\.html"[^>]*title="([^"]*)"[^>]*'
            r'aria-label="([^"]*)"', html):
        offer_id, title_attr, aria = m.group(1), m.group(2), m.group(3)
        if offer_id in seen:
            continue
        seen.add(offer_id)
        aria = htmllib.unescape(aria)
        am = re.search(
            r"Voir offre de (.+?) à (.+?), chez (.+?), pour un[e]? ([^,]+)", aria)
        window = html[max(0, m.start() - 2500):m.start() + 2500]
        dm = re.search(r"il y a\s+\d+\s+jours?|aujourd'hui|\bhier\b", window, re.I)
        cards.append({
            "source": "hellowork", "offer_id": offer_id,
            "url": f"https://www.hellowork.com/fr-fr/emplois/{offer_id}.html",
            "title": (am.group(1) if am else htmllib.unescape(title_attr)).strip(),
            "company_name": (am.group(3).strip() if am else
                             htmllib.unescape(title_attr).rsplit(" - ", 1)[-1].strip()),
            "location": am.group(2).strip() if am else "",
            "contract_type": am.group(4).strip() if am else None,
            "description": "",
            "posted_date": parse_date(dm.group(0)) if dm else None,
        })
    return cards


def hw_detail(offer):
    html = fetch(offer["url"])
    if not html:
        return offer
    m = re.search(r'"datePosted"\s*:\s*"([\d\-T:+]+)"', html) or \
        re.search(r"Publiée? le\s+(\d{1,2}\s+\w+\s+\d{4})", html, re.I)
    if m:
        offer["posted_date"] = parse_date(m.group(1)) or offer["posted_date"]
    m = re.search(r'"description"\s*:\s*"(.{80,2000}?)"', html)
    if m:
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>|\\n|\\u003c[^\\]*\\u003e", " ",
                      m.group(1))).strip()
        offer["description"] = htmllib.unescape(text)[:800]
    return offer


# ---------------------------------------------------------------- career pages

def careerpage_probe(company):
    """Homepage + likely career paths; returns offer-shaped hits (≤3 fetches)."""
    domain = (company.get("domain") or "").strip().strip("/")
    if not domain:
        return []
    base = domain if domain.startswith("http") else f"https://{domain}"
    budget, hits = 3, []
    home = fetch(base)
    budget -= 1
    candidates = []
    if home:
        for m in re.finditer(r'href="([^"]*(?:recrut|carri|emploi|rejoin|jobs)[^"]*)"',
                             home, re.I):
            candidates.append(urllib.parse.urljoin(base + "/", m.group(1)))
        if HIRING_WORDS.search(re.sub(r"<[^>]+>", " ", home)):
            hits.append((base, home))
    for path in list(dict.fromkeys(candidates))[:2] + \
            [f"{base}/{p}" for p in CAREER_PATHS]:
        if budget <= 0:
            break
        if any(h[0] == path for h in hits):
            continue
        page = fetch(path)
        budget -= 1
        if page and HIRING_WORDS.search(re.sub(r"<[^>]+>", " ", page)):
            hits.append((path, page))
            break
    offers = []
    # prefer the deep career page over the homepage: better evidence for a
    # human, and a stable signal key (field-tested duplicate: homepage vs
    # deep page produced two sig_keys for the same hiring)
    deep = [h for h in hits if h[0] != base]
    for url, page in (deep or hits)[:1]:
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page))
        kw = HIRING_WORDS.search(text)
        window = text[max(0, kw.start() - 150):kw.start() + 350] if kw else text[:400]
        posted = None
        m = re.search(r'"datePosted"\s*:\s*"([\d\-T:+]+)"', page)
        if m:
            posted = parse_date(m.group(1))
        offers.append({
            "source": "careerpage", "offer_id": url, "url": url,
            "title": "career page hiring mention",
            "company_name": company.get("name", ""),
            "location": company.get("location", ""),
            "description": window.strip(), "posted_date": posted,
            "contract_type": None,
        })
    return offers


# ---------------------------------------------------------------- pipeline

def prescore(offer):
    days = recency_days(offer.get("posted_date"))
    pts, detail = 0, {}
    if days is not None:
        detail["recency"] = 20 if days <= 7 else 12 if days <= 30 else \
            6 if days <= 60 else 0
        pts += detail["recency"]
    if offer.get("tool_hits"):
        detail["tools"] = 15
        pts += 15
    if offer.get("pain_hits"):
        detail["pains"] = 15
        pts += 15
    offer["recency_days"] = days
    offer["prescore65"] = pts        # +15 volume is company-level, +35 is LLM
    offer["prescore_detail"] = detail
    return offer


def triage(offers, matrix, keep_agencies):
    kept, rejected, seen = [], [], set()
    negative = matrix.get("negative", [])
    for o in offers:
        key = (o["source"], o["offer_id"])
        xkey = (norm(o["title"]), norm(o["company_name"]))
        if key in seen or (all(xkey) and xkey in seen):
            continue
        seen.add(key)
        if all(xkey):
            seen.add(xkey)
        o["tool_hits"] = keyword_hits(o["title"] + " " + o["description"],
                                      matrix.get("tools", []))
        o["pain_hits"] = keyword_hits(o["title"] + " " + o["description"],
                                      matrix.get("pains", []))
        prescore(o)
        vt = o.pop("valid_through", None)
        if vt and parse_date(vt) and parse_date(vt) < TODAY.isoformat():
            o["reject_reason"] = "expired"
        elif not o["company_name"]:
            o["reject_reason"] = "anonymous employer"
        elif STAGE_RE.search(o["title"]) or \
                (o.get("contract_type") and STAGE_RE.search(o["contract_type"])):
            o["reject_reason"] = "stage/alternance"
        else:
            brand = agency_suspect(o["company_name"], o["title"], negative)
            if brand and not keep_agencies:
                o["reject_reason"] = f"staffing agency ({brand})"
        if o.get("recency_days") is not None and o["recency_days"] > 60:
            o.setdefault("reject_reason", "older than 60 days")
        (rejected if o.get("reject_reason") else kept).append(o)
    kept.sort(key=lambda x: (-x["prescore65"],
                             x["recency_days"] if x["recency_days"] is not None else 999))
    return kept, rejected


def group_by_company(offers):
    groups = {}
    for o in offers:
        g = groups.setdefault(norm(o["company_name"]), {
            "company_name": o["company_name"], "offers": [], "n_offers": 0,
            "freshest": None, "tool_hits": set(), "pain_hits": set(),
        })
        g["offers"].append(o["offer_id"])
        g["n_offers"] += 1
        if o.get("posted_date") and (g["freshest"] is None or
                                     o["posted_date"] > g["freshest"]):
            g["freshest"] = o["posted_date"]
        g["tool_hits"] |= set(o["tool_hits"])
        g["pain_hits"] |= set(o["pain_hits"])
        g["prescore65"] = max(g.get("prescore65", 0), o["prescore65"])
    out = []
    for g in groups.values():
        if g["n_offers"] >= 2:
            g["prescore65"] = min(65, g["prescore65"] + 15)  # volume bonus
            g["volume_bonus"] = 15
        g["tool_hits"], g["pain_hits"] = sorted(g["tool_hits"]), sorted(g["pain_hits"])
        out.append(g)
    out.sort(key=lambda g: -g["prescore65"])
    return out


def fetch_details(offers, max_details, workers=1):
    """Spend the detail budget on the most promising undated cards first.

    Target selection is identical to the serial version (walk the ranked
    list, same budget rules); only the fetches run in parallel — each
    thread mutates a distinct offer dict, so no locking is needed."""
    ranked = sorted(offers, key=lambda o: (-(len(o["pain_hits"]) + len(o["tool_hits"])),
                                           o["posted_date"] is not None))
    targets = []
    for o in ranked:
        if len(targets) >= max_details:
            break
        if o["source"] == "francetravail":
            targets.append((ft_detail, o))
        elif o["source"] == "hellowork" and not o["posted_date"]:
            targets.append((hw_detail, o))
    pmap(lambda detail, offer: detail(offer), targets, workers)
    return offers


def write_out(outdir, kept, rejected, companies, summary):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in [("offers.jsonl", kept), ("rejected.jsonl", rejected),
                       ("companies.jsonl", companies)]:
        with open(out / name, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary["spend_credits"] = 0
    summary["fetches"] = state["fetches"]
    summary["errors"] = state["errors"][:20]
    if state.get("t0") is not None:
        summary["elapsed_s"] = round(time.perf_counter() - state["t0"], 1)
    with open(out / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False))


def run_hunt(args):
    matrix = json.load(open(args.matrix, encoding="utf-8"))
    titles = matrix.get("titles") or sys.exit("matrix.titles is required")
    locations = matrix.get("locations") or [""]
    sources = matrix.get("sources") or ["francetravail", "hellowork"]
    queries, raw = [], []
    for title in titles:
        for loc in locations:
            for src in sources:
                queries.append((src, title, loc))
    queries = queries[:args.max_queries]

    def one_query(src, title, loc):
        log(f"[hunt] {src}: {title} @ {loc or 'France'}")
        return (ft_search if src == "francetravail" else hw_search)(title, loc)

    for cards in pmap(one_query, queries, args.workers):
        raw += cards
    # triage once for keyword hits, fetch details on survivors, triage again
    kept, rejected = triage(raw, matrix, args.keep_agencies)
    fetch_details(kept, args.max_details, args.workers)
    kept, late_rejects = triage(kept, matrix, args.keep_agencies)
    rejected += late_rejects
    companies = group_by_company(kept)
    write_out(args.out, kept, rejected, companies, {
        "mode": "hunt", "queries_run": len(queries), "raw_offers": len(raw),
        "kept": len(kept), "rejected": len(rejected),
        "companies": len(companies),
        "reject_reasons": count_reasons(rejected),
    })


def match_company(card_employer, companies):
    """Map an offer's employer to one of the tracked companies, or None."""
    got = norm(card_employer)
    if not got:
        return None
    for c in companies:
        wanted = norm(c.get("name", ""))
        if wanted and (got in wanted or wanted in got):
            return c
    return None


def run_check(args):
    rows = json.load(open(args.companies, encoding="utf-8"))
    matrix = {"tools": [], "pains": [], "negative": []}
    all_kept, all_rejected, verdicts = [], [], []

    # one trade-keyword sweep serves the whole batch: FT matches employers
    # poorly by name (field-tested), but métier queries surface them
    swept = {}
    keywords = [k.strip() for k in (args.keywords or "").split(",") if k.strip()]
    if keywords:
        locations = sorted({c.get("location", "") for c in rows})

        def sweep_one(kw, loc):
            log(f"[check-sweep] {kw} @ {loc or 'France'}")
            return ft_search(kw, loc)

        sweep_jobs = [(kw, loc) for kw in keywords for loc in locations]
        for cards in pmap(sweep_one, sweep_jobs, args.workers):
            for card in cards:
                owner = match_company(card["company_name"], rows)
                if owner is not None:
                    swept.setdefault(id(owner), []).append(card)

    def check_one(c):
        # swept is read-only here; each thread works its own company dict.
        # Inner fetch_details stays serial (≤3 fetches) — the parallelism
        # is across companies, no nested pools.
        log(f"[check] {c.get('name')}")
        raw = list(swept.get(id(c), []))
        cards = ft_search(c.get("name", ""), c.get("location", ""))
        for card in cards:
            if match_company(card["company_name"], [c]) is not None:
                raw.append(card)
        raw += careerpage_probe(c)
        kept, rejected = triage(raw, matrix, keep_agencies=True)
        fetch_details(kept, max_details=min(3, args.max_details))
        kept, late = triage(kept, matrix, keep_agencies=True)
        rejected += late
        for o in kept + rejected:
            o["company_id"] = c.get("company_id")
        freshest = max((o["posted_date"] for o in kept if o["posted_date"]),
                       default=None)
        verdict = {
            "company_id": c.get("company_id"), "company_name": c.get("name"),
            "found": len(kept), "freshest": freshest,
            "verdict": "hiring" if kept else "quiet",
            "offers": [o["offer_id"] for o in kept],
        }
        return kept, rejected, verdict

    for kept, rejected, verdict in pmap(check_one, [(c,) for c in rows],
                                        args.workers):
        verdicts.append(verdict)
        all_kept += kept
        all_rejected += rejected
    write_out(args.out, all_kept, all_rejected, verdicts, {
        "mode": "check", "companies_checked": len(rows),
        "hiring": sum(1 for v in verdicts if v["verdict"] == "hiring"),
        "quiet": sum(1 for v in verdicts if v["verdict"] == "quiet"),
        "kept": len(all_kept), "rejected": len(all_rejected),
        "reject_reasons": count_reasons(all_rejected),
    })


def count_reasons(rejected):
    counts = {}
    for o in rejected:
        counts[o["reject_reason"]] = counts.get(o["reject_reason"], 0) + 1
    return counts


def main():
    state["t0"] = time.perf_counter()
    p = argparse.ArgumentParser(description="Hiring-signal hunt engine")
    sub = p.add_subparsers(dest="mode", required=True)
    hunt = sub.add_parser("hunt", help="matrix-driven sourcing (find-hiring-signal)")
    hunt.add_argument("--matrix", required=True)
    check = sub.add_parser("check", help="per-company sweep (signal-person pass 3)")
    check.add_argument("--companies", required=True)
    check.add_argument("--keywords", default="",
                       help="comma-separated trade keywords swept once for the "
                            "whole batch (FT matches employer names poorly)")
    for s in (hunt, check):
        s.add_argument("--out", required=True)
        s.add_argument("--max-queries", type=int, default=30)
        s.add_argument("--max-details", type=int, default=40)
        s.add_argument("--keep-agencies", action="store_true")
        s.add_argument("--workers", type=int, default=6,
                       help="parallel fetches; per-host politeness is kept "
                            "by the shared limiter (default 6)")
    args = p.parse_args()
    (run_hunt if args.mode == "hunt" else run_check)(args)


if __name__ == "__main__":
    main()
