#!/usr/bin/env python3
"""Firmographics adapter — French government company search API.

Free, no API key, official (recherche-entreprises.api.gouv.fr), rate limit
7 req/s. Used by the enrich-firmographics skill. Fetch only: this tool
NEVER touches bricks.db — results go through the db-writer agent.

Usage:
    python3 firmo.py --name "Fleux" [--hint "75004 fleux.com"]
    python3 firmo.py --stdin        # JSONL rows: {"_id": 3, "name": "...", "hint": "..."}

Output: one JSON object per input (JSONL on --stdin) with:
    confidence  high | ambiguous | none
    siren, legal_name, naf, industry (NAF section label), employees
    (range string), employees_year, city, postal, country, executives
    (list of {name, role}, statutory auditors filtered out)
    candidates  (only when ambiguous: up to 3 {siren, legal_name, city})
"""

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

API = "https://recherche-entreprises.api.gouv.fr/search"
RATE_SLEEP = 0.16  # stay under 7 req/s

EFFECTIF = {
    "00": "0", "01": "1-2", "02": "3-5", "03": "6-9", "11": "10-19",
    "12": "20-49", "21": "50-99", "22": "100-199", "31": "200-249",
    "32": "250-499", "41": "500-999", "42": "1000-1999", "51": "2000-4999",
    "52": "5000-9999", "53": "10000+",
}

NAF_SECTIONS = [
    ((1, 3), "Agriculture"), ((5, 9), "Extractive industries"),
    ((10, 33), "Manufacturing"), ((35, 35), "Energy"),
    ((36, 39), "Water & waste"), ((41, 43), "Construction"),
    ((45, 47), "Trade & retail"), ((49, 53), "Transport & logistics"),
    ((55, 56), "Hospitality & food"), ((58, 63), "Information & communication"),
    ((64, 66), "Finance & insurance"), ((68, 68), "Real estate"),
    ((69, 75), "Professional services"), ((77, 82), "Administrative services"),
    ((84, 84), "Public administration"), ((85, 85), "Education"),
    ((86, 88), "Health & social work"), ((90, 93), "Arts & entertainment"),
    ((94, 96), "Other services"), ((97, 98), "Households"),
    ((99, 99), "Extra-territorial"),
]

EXCLUDED_ROLES = re.compile(r"commissaire", re.IGNORECASE)
LEGAL_FORMS = {"sas", "sasu", "sarl", "eurl", "sa", "sci", "snc", "scop", "sel", "selarl"}
PARENT_ROLES = re.compile(r"pr[ée]sident|g[ée]rant", re.IGNORECASE)


def normalize(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def simplified(name):
    tokens = [t for t in normalize(name).split() if t not in LEGAL_FORMS]
    return " ".join(tokens[:2])


def naf_section(naf):
    try:
        division = int(str(naf)[:2])
    except (ValueError, TypeError):
        return None
    for (lo, hi), label in NAF_SECTIONS:
        if lo <= division <= hi:
            return label
    return None


def executives_of(record):
    people, parent = [], None
    for d in record.get("dirigeants", []):
        role = (d.get("qualite") or "").strip()
        if EXCLUDED_ROLES.search(role):
            continue
        name = " ".join(p for p in [
            (d.get("prenoms") or "").strip().title(),
            (d.get("nom") or "").strip().title(),
        ] if p)
        entity = False
        if not name:
            name = (d.get("denomination") or "").strip()
            entity = bool(name)
        if name:
            person = {"name": name, "role": role}
            if entity:
                person["entity"] = True
                if parent is None and PARENT_ROLES.search(role):
                    parent = name
            people.append(person)
    return people, parent


def shape(record):
    siege = record.get("siege") or {}
    code = record.get("tranche_effectif_salarie")
    executives, parent = executives_of(record)
    out = {
        "siren": record.get("siren"),
        "legal_name": record.get("nom_complet"),
        "company_category": record.get("categorie_entreprise"),
        "naf": record.get("activite_principale"),
        "industry": naf_section(record.get("activite_principale")),
        "employees": EFFECTIF.get(code),
        "employees_year": record.get("annee_tranche_effectif_salarie"),
        "city": siege.get("libelle_commune"),
        "postal": siege.get("code_postal"),
        "country": "FR",
        "executives": executives,
    }
    if parent:
        out["parent_company"] = parent
    return out


def score(record, wanted_norm, hint_norm):
    got = normalize(record.get("nom_complet"))
    s = 0.0
    if got == wanted_norm:
        s += 2.0
    elif wanted_norm and (wanted_norm in got or got in wanted_norm):
        s += 1.0
    if hint_norm:
        siege = record.get("siege") or {}
        haystack = normalize(" ".join(str(v) for v in [
            siege.get("libelle_commune"), siege.get("code_postal"),
            record.get("nom_complet"),
        ]))
        if any(tok in haystack for tok in hint_norm.split() if len(tok) > 2):
            s += 1.0
    return s


def fetch(q, extra=None):
    params = {"q": q, "page": 1, "per_page": 5}
    if extra:
        params.update(extra)
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{API}?{query}", headers={"User-Agent": "bricks-firmographics"}
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response).get("results", [])


def lookup(name, hint="", siren=""):
    siren = re.sub(r"\D", "", str(siren or ""))
    postal = re.search(r"\b(\d{5})\b", hint or "")
    postal_filter = {"code_postal": postal.group(1)} if postal else None
    try:
        if len(siren) == 9:
            for record in fetch(siren):
                if record.get("siren") == siren:
                    out = shape(record)
                    out["confidence"] = "high"
                    return out
            return {"confidence": "none", "error": "siren not found"}
        results = fetch(name, postal_filter)
        if not results and postal_filter:
            time.sleep(RATE_SLEEP)
            results = fetch(name)
        if not results and simplified(name) not in ("", normalize(name)):
            time.sleep(RATE_SLEEP)
            results = fetch(simplified(name), postal_filter)
            if not results and postal_filter:
                time.sleep(RATE_SLEEP)
                results = fetch(simplified(name))
    except Exception as e:
        return {"confidence": "none", "error": f"api error: {e}"}

    if not results:
        return {"confidence": "none"}

    wanted, hinted = normalize(name), normalize(hint)
    ranked = sorted(results, key=lambda r: score(r, wanted, hinted), reverse=True)
    best, best_score = ranked[0], score(ranked[0], wanted, hinted)
    runner_up = score(ranked[1], wanted, hinted) if len(ranked) > 1 else -1.0

    if best_score >= 2.0 and (best_score - runner_up) >= 1.0:
        confidence = "high"
    elif len(results) == 1 and best_score >= 1.0:
        confidence = "high"
    else:
        return {
            "confidence": "ambiguous",
            "candidates": [
                {
                    "siren": r.get("siren"),
                    "legal_name": r.get("nom_complet"),
                    "city": (r.get("siege") or {}).get("libelle_commune"),
                }
                for r in ranked[:3]
            ],
        }

    out = shape(best)
    out["confidence"] = confidence
    return out


def main():
    parser = argparse.ArgumentParser(description="French firmographics lookup")
    parser.add_argument("--name")
    parser.add_argument("--hint", default="")
    parser.add_argument("--stdin", action="store_true",
                        help="read JSONL rows {_id, name, hint} from stdin")
    args = parser.parse_args()

    if args.stdin:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            result = lookup(row.get("name", ""), row.get("hint", ""),
                            row.get("siren", ""))
            result["_id"] = row.get("_id")
            print(json.dumps(result, ensure_ascii=False), flush=True)
            time.sleep(RATE_SLEEP)
    elif args.name:
        print(json.dumps(lookup(args.name, args.hint), ensure_ascii=False))
    else:
        parser.error("--name or --stdin required")


if __name__ == "__main__":
    main()
