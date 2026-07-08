#!/usr/bin/env python3
"""FullEnrich people-search fetcher — deterministic adapter for runner.py.

Called per row by `runner.py run --action fetch --fetcher fullenrich_people`.
Pure HTTP (their public API, Bearer key) — no MCP, no model. The
INTELLIGENCE lives upstream: the skill compiles params.json ONCE (title
waves = strict synonyms of the SAME activity, seniority codes, caps); this
adapter only executes the cascade, mechanically, per company:

    wave 1 (the user's words + tightest synonyms) → hits? stop.
    wave 2 (close synonyms, same activity)        → hits? stop.
    wave 3 (broader names of the same activity)   → hits? stop. else not_found.

Stopping at the FIRST wave with verified hits keeps precision: waves are
fallback vocabulary for the same person, never a widening of WHO we hunt.
Several explicit roles ("des SDR ET des CEO") = several GROUPS, each with
its own waves and cap — never mixed into one soup.

params.json contract (written by the calling skill, CONVENTIONS §11):
    {"groups": [
       {"label": "growth", "role_type": "champion",
        "seniority": ["Head", "VP", "Director", "Manager"],
        "title_waves": [["gtm growth engineer", "growth engineer"],
                        ["head of growth", "growth lead", "growth marketer"]],
        "cap": 3}
     ]}

Env: FULLENRICH_API_KEY (Bearer — dashboard key, NOT the MCP OAuth);
     FULLENRICH_API_URL overrides the endpoint (tests use a local stub).

Cost note (field-measured): the DIRECT API bills ~0.25 credit per search
call (metadata.credits) — unlike the MCP search_people, which is free.
The cascade only re-queries a company on the waves its previous waves
MISSED, and inserted people dedup on person_key across runs — so multiple
waves (e.g. English + French titles on a FR market) never pay twice for
a company already resolved and never insert the same person twice.

fetch(row, params) -> outcome:
    {"status": "done" | "not_found" | "failed",
     "rows": [{full_name, role, seniority, linkedin_url, role_type,
               role_query}],                      # verified people only
     "evidence": "growth: 2 via vague 1 · 3 crédits",
     "error": "...",                              # failed only
     "credits": 3}                                # metadata.credits summed

Verification rule (§ house doctrine): current employment domain must be
OUR domain, full name unmasked (a provider-masked "Hakim A." is never
returned), title present. Ambiguity beyond the cap is the caller's job.
This tool NEVER touches bricks.db.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import envfile  # noqa: E402

envfile.load()  # ~/.bricks/env → FULLENRICH_API_KEY without shell exports

DEFAULT_API_URL = "https://app.fullenrich.com/api/v2/people/search"
TIMEOUT = 30
#: Field-measured (2026-07, 283-company run): 0.35 s → HTTP 429 storms even
#: SERIAL (223/271 rows failed, then 163 still failed at 0.35 s); 2 s passed
#: with 0 failures. Their limiter answers "try again in 1m" when abused.
RATE_SLEEP = 2.0
RETRY_429_SLEEP = 30  # one polite retry per call before failing the row


class RateLimiter:
    """Shared token gate: request starts stay RATE_SLEEP apart process-wide."""

    def __init__(self, interval):
        self.interval = interval
        self._lock = threading.Lock()
        self._next_at = 0.0

    def acquire(self):
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next_at)
            self._next_at = start + self.interval
        if start > now:
            time.sleep(start - now)


LIMITER = RateLimiter(RATE_SLEEP)


def norm(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def masked(full_name: str) -> bool:
    """Provider-masked last names ('Hakim A.') are unusable downstream."""
    parts = [p for p in full_name.split() if p.strip()]
    if len(parts) < 2:
        return True
    return len(parts[-1].strip(".")) <= 1


def call_api(domain: str, titles: list, seniority: list | None,
             limit: int, key: str) -> dict:
    # The API wants FILTER OBJECTS ({"value": ...}), not raw strings —
    # field-tested 2026-07: raw strings answer HTTP 400 on every call (a
    # desktop run diagnosed it live with a curl A/B and patched its local
    # cache; this is that fix, in the repo where it survives updates).
    body = {"current_company_domains": [{"value": domain}],
            "current_position_titles": [{"value": t} for t in titles],
            "limit": limit}
    if seniority:
        body["current_position_seniority_level"] = [
            {"value": s} for s in seniority]
    request = urllib.request.Request(
        os.environ.get("FULLENRICH_API_URL", DEFAULT_API_URL),
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "User-Agent": "bricks-fullenrich-people"},
        method="POST")
    for attempt in (1, 2):
        LIMITER.acquire()
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            # 429 = their limiter — one polite retry, then the row fails
            # cleanly (an explicit --retry-failed pass picks it up).
            if exc.code == 429 and attempt == 1:
                time.sleep(RETRY_429_SLEEP)
                continue
            raise


def accept(person: dict, domain: str) -> dict | None:
    """Name + current employment must cohere with OUR company, unmasked."""
    current = (person.get("employment") or {}).get("current") or {}
    company = current.get("company") or {}
    person_domain = (company.get("domain") or "").lower().strip()
    if person_domain != domain:
        return None
    name = (person.get("full_name") or "").strip()
    if not name or masked(name):
        return None
    title = (current.get("title") or "").strip()
    if not title:
        return None
    network = (person.get("social_profiles") or {}).get(
        "professional_network") or {}
    return {"full_name": name, "role": title,
            "seniority": current.get("seniority"),
            "linkedin_url": network.get("url")}


def fetch(row: dict, params: dict) -> dict:
    key = os.environ.get("FULLENRICH_API_KEY", "").strip()
    if not key:
        return {"status": "failed", "rows": [], "credits": 0,
                "error": "FULLENRICH_API_KEY absent de l'environnement "
                         "(clé API du dashboard FullEnrich)"}
    domain = (row.get("domain") or "").strip().lower()
    if not domain:
        return {"status": "failed", "rows": [], "credits": 0,
                "error": "input manquant : domain"}

    people, credits, notes = [], 0, []
    try:
        for group in params.get("groups", []):
            cap = int(group.get("cap", 3))
            found = []
            for wave_number, wave in enumerate(group.get("title_waves", []), 1):
                if not wave:
                    continue
                data = call_api(domain, wave, group.get("seniority"),
                                min(max(cap * 3, 10), 25), key)
                # credits are FRACTIONAL (~0.25/search call) — int() silently
                # truncated them to 0 and the receipts under-reported spend
                credits += float((data.get("metadata") or {}).get("credits") or 0)
                for person in data.get("people", []):
                    kept = accept(person, domain)
                    if kept is None:
                        continue
                    if any(norm(kept["full_name"]) == norm(f["full_name"])
                           for f in found):
                        continue
                    kept["role_type"] = group.get("role_type")
                    kept["role_query"] = f"{group.get('label', 'g')}/vague{wave_number}"
                    found.append(kept)
                    if len(found) >= cap:
                        break
                if found:
                    notes.append(f"{group.get('label', 'g')}: {len(found)} "
                                 f"via vague {wave_number}")
                    break  # first wave with verified hits wins — precision
            people += found
    except (urllib.error.URLError, urllib.error.HTTPError, OSError,
            json.JSONDecodeError, ValueError) as exc:
        return {"status": "failed", "rows": [], "credits": round(credits, 2),
                "error": f"api error: {exc}"}

    if not people:
        return {"status": "not_found", "rows": [], "credits": round(credits, 2),
                "evidence": f"aucune vague concluante · {credits} crédits"}
    return {"status": "done", "rows": people, "credits": round(credits, 2),
            "evidence": " · ".join(notes) + f" · {credits} crédits"}
