#!/usr/bin/env python3
"""FullEnrich people-search — deterministic provider step for runner.py.

Free of any model: pure HTTP (their public API, Bearer key). The
INTELLIGENCE lives upstream: the skill compiles a params JSON file ONCE
(title waves = strict synonyms of the SAME activity, seniority codes,
caps); this step only executes the cascade, mechanically, per company:

    wave 1 (the user's words + tightest synonyms) → hits? stop.
    wave 2 (close synonyms, same activity)        → hits? stop.
    wave 3 (broader names of the same activity)   → hits? stop. else nothing.

Stopping at the FIRST wave with verified hits keeps precision: waves are
fallback vocabulary for the same person, never a widening of WHO we hunt.
Several explicit roles ("des SDR ET des CEO") = several GROUPS, each with
its own waves and cap — never mixed into one soup.

params JSON (written by the calling skill):
    {"groups": [
       {"label": "growth", "role_type": "champion",
        "seniority": ["Head", "VP", "Director", "Manager"],
        "title_waves": [["gtm growth engineer", "growth engineer"],
                        ["head of growth", "growth lead", "growth marketer"]],
        "cap": 3}
     ]}

Runner step (per company row, reads row["domain"]):
    export FULLENRICH_PARAMS=/abs/path/params.json   # compiled by the skill
    export FULLENRICH_OUT_TABLE=people               # child table (default)
    python3 runner.py --table companies --step tools/providers/fullenrich.py:step \
        --status-col people_status
    # preview: returns people_found / people_evidence / people (JSON, for review)
    # commit:  inserts verified people as CHILD ROWS in FULLENRICH_OUT_TABLE
    #          (dedup key linkedin_url) and writes people_found / people_evidence
    #          on the company row

One-off CLI:
    python3 fullenrich.py --domain acme.fr --params params.json

Env: FULLENRICH_API_KEY (Bearer — dashboard key, NOT the MCP OAuth);
     FULLENRICH_API_URL overrides the endpoint (tests use a local stub).

Verification rule (house doctrine): current employment domain must be OUR
domain, full name unmasked (a provider-masked "Hakim A." is never
returned), title present. Ambiguity beyond the cap is the caller's job.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.request

_CORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core")
sys.path.insert(0, os.path.abspath(_CORE))
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


def search(domain: str, params: dict) -> dict:
    """Run the wave cascade for one domain. Raises on API/config failure."""
    key = os.environ.get("FULLENRICH_API_KEY", "").strip()
    if not key:
        raise RuntimeError("FULLENRICH_API_KEY absent de l'environnement "
                           "(clé API du dashboard FullEnrich)")
    domain = (domain or "").strip().lower()
    if not domain:
        raise ValueError("missing input column 'domain' for this row")

    people, credits, notes = [], 0, []
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

    credits = round(credits, 2)
    evidence = (" · ".join(notes) if notes
                else "aucune vague concluante") + f" · {credits} crédits"
    return {"people": people, "credits": credits, "evidence": evidence}


# --------------------------------------------------------------------------
# Runner step contract — step(row, ctx) -> dict
# --------------------------------------------------------------------------

_params_cache: dict = {}


def _params(args: dict) -> dict:
    """Search params: inline in the step args, a file path, or the legacy env."""
    inline = args.get("params")
    if isinstance(inline, dict):
        loaded = inline
        cache_key = None
    else:
        path = (inline or os.environ.get("FULLENRICH_PARAMS", "")).strip()
        if not path:
            raise RuntimeError('step needs {"params": {...}|"path.json"} in its '
                               "args (or FULLENRICH_PARAMS in the env)")
        if path in _params_cache:
            return _params_cache[path]
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
        cache_key = path
    if not loaded.get("groups"):
        raise RuntimeError("params JSON needs a non-empty 'groups' list")
    if cache_key:
        _params_cache[cache_key] = loaded
    return loaded


def step(row: dict, ctx: dict, args: dict = None) -> dict:
    args = args or {}
    out = search(row.get("domain", ""), _params(args))
    fields = {"people_found": len(out["people"]),
              "people_evidence": out["evidence"]}
    if not out["people"]:
        return fields
    if ctx.get("commit") or ctx.get("preview"):
        import db as dbmod  # core is already on sys.path
        table = (args.get("out_table") or ctx.get("out_table")
                 or os.environ.get("FULLENRICH_OUT_TABLE", "").strip() or "people")
        children = [{**p, "company_id": row.get("_id"),
                     "company_domain": (row.get("domain") or "").strip().lower(),
                     "source_run": ctx.get("run_id")}
                    for p in out["people"]]
        dbmod.add(ctx["db"], table, children, key="linkedin_url")
    else:
        fields["people"] = json.dumps(out["people"], ensure_ascii=False)
    return fields


def main():
    parser = argparse.ArgumentParser(description="FullEnrich people search (one domain)")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--params", required=True, help="params JSON file")
    args = parser.parse_args()
    try:
        with open(args.params, encoding="utf-8") as f:
            params = json.load(f)
        out = search(args.domain, params)
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError,
            urllib.error.URLError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False),
              file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **out}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
