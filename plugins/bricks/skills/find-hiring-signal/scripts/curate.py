#!/usr/bin/env python3
"""Frozen curation kernel — Phase 2/3 of find-hiring-signal, deterministic.

jobs.py hunt produces the raw staging (offers.jsonl + companies.jsonl,
mechanical prescore /65). What happened next used to be re-derived by the
session model at every run: role scoring, agency/public/mega filtering, the
relative cut, the outreach angle. A field run re-invented that crible as an
ad-hoc script with a case-sensitivity bug (105 valid finance roles rejected)
and spent ~25 minutes debugging it. This file freezes the whole step — same
staging + same matrix = same output, in milliseconds, forever.

The session model's judgment moves AFTER this script: review the receipt's
distribution and samples, override by exception (a wrongly rejected company
is re-added by hand) — it never rewrites the crible.

CLI (JSON receipt on stdout; on error JSON on stderr + exit 1):
    python3 curate.py run --staging <jobs.py hunt outdir> --matrix matrix.json \
        --out <rundir> [--today YYYY-MM-DD]
    python3 curate.py emit-signals --committed <rundir>/committed.jsonl \
        --ids <db.py select JSON: _id,name> --out signals_payload.json \
        [--today YYYY-MM-DD]

`run` writes to --out:
    committed.jsonl / parked.jsonl / rejected.jsonl   (audit trail)
    companies_payload.json    ready for: db.py add companies --rows - --key name

`emit-signals` joins committed companies to their freshly-inserted _id
(by normalized name) and writes the signals rows — company_id ALWAYS set
(field-tested: orphaned signals sank the strongest accounts), sig_key
normalized per CONVENTIONS (scheme/www stripped, no trailing slash) —
ready for: db.py add signals --rows - --key sig_key

Matrix additions read by this script (all optional, defaults below):
    "role_groups": {"finance": {"points": 25, "titles": [...], "angle": "..."},
                    "terrain": {"points": 15, "titles": [...], "angle": "..."}}
    "exclude_employers": ["..."]      extra employer names to reject
    "exclude_public": true            reject public/nonprofit employers

The cut is RELATIVE, measured on the batch (SKILL Phase 3): reachable =
100 − 10 (size, never visible in an ad) − 15 if the tool criterion never
fires on this channel (<5 % of offers) − 15 if volume never fires (<10 %
of companies have ≥2 offers). commit ≥ 65 % of reachable, park ≥ 45 %.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "..", "tools"))
import jobs  # norm(), agency_suspect(), AGENCY/NAME_AGENCY tokens

DEFAULT_ROLE_GROUPS = {
    "finance": {
        "points": 25,
        "titles": ["chef comptable", "responsable comptable",
                   "responsable administratif et financier",
                   "directeur administratif et financier",
                   "directeur financier", "raf", "daf",
                   "controleur de gestion", "comptable unique", "comptable"],
        "angle": ("Vous renforcez votre fonction finance ({roles}){pains} : "
                  "c'est le moment où le traitement manuel des notes de frais "
                  "devient le goulot de la clôture. Un mot sur l'automatisation "
                  "capture + TVA + export compta ?"),
    },
    "terrain": {
        "points": 15,
        "titles": ["commercial terrain", "commercial itinerant",
                   "technico-commercial", "attache commercial",
                   "technicien itinerant", "commercial b to b"],
        "angle": ("Vous étoffez votre force terrain ({roles}, {n} poste(s)) : "
                  "plus de collaborateurs en déplacement = plus de notes de "
                  "frais. On dématérialise la saisie mobile et on accélère "
                  "les remboursements ?"),
    },
}

#: The industry-proof staffing detector: whatever a cabinet calls itself
#: (yesterday "Intérim", today "Talents", tomorrow anything), its OFFER TEXT
#: gives it away — it recruits "pour notre client". Matched on the norm'd
#: title+description of every offer (field-tested: Voluntae, Noviac, Huca
#: Group carried no name token at all and polluted a whole base).
DESC_AGENCY_RE = re.compile(
    r"\b(pour (notre|l un de nos|le compte d un|le compte de (notre|nos)) client|"
    r"notre client|nos clients|"
    r"cabinet (de recrutement|de conseil|d expertise comptable|comptable)|"
    r"agence (de recrutement|d emploi|d interim)|"
    r"(nous|on) recrutons? pour|"
    r"specialis\w+ (en|du|dans le) recrutement|"
    r"acteur (majeur )?(du recrutement|de l interim)|"
    r"conseil en recrutement|super recruteur|"
    r"notre cabinet|le cabinet recherche|"
    r"portefeuille de dossiers|nos mandants)\b")

#: Expertise-comptable job-title fingerprint: these titles exist ONLY in
#: cabinets — an in-house hire is a "comptable", never a "chef de mission"
#: or a "collaborateur comptable" (field-tested: a run had to hand-kill
#: them one by one). Matched on the norm'd offer TITLE.
TITLE_CABINET_RE = re.compile(
    r"\b(chef de mission|collaborateur comptable|collaboratrice comptable|"
    r"chef de mission expertise)\b")

#: Public / nonprofit employers — killable at sourcing (matrix
#: exclude_public=false disables). Matched word-boundary on the norm'd name.
PUBLIC_RE = re.compile(
    r"\b(mairie|ville de|commune|communaute|agglomeration|metropole|"
    r"conseil departemental|conseil regional|prefecture|ministere|"
    r"universite|lycee|college|academie|rectorat|chu|hopital|hospitalier|"
    r"ehpad|ccas|caf|cpam|urssaf|pole emploi|france travail|gendarmerie|"
    r"association|fondation|federation|syndicat|diocese)\b")

#: Obvious >250 groups seen crossing field runs — a prefilter, not a census:
#: anything wrongly caught lands in rejected.jsonl with its reason, visible
#: and re-addable by hand. Firmographics remains the real size gate.
MEGA_EMPLOYERS = [
    "bouygues", "eiffage", "vinci", "saint gobain", "aldi", "lidl",
    "carrefour", "auchan", "leclerc", "intermarche", "sncf", "ratp", "edf",
    "engie", "orange", "totalenergies", "bnp paribas", "societe generale",
    "credit agricole", "axa", "allianz", "mgen", "spie", "equans", "veolia",
    "suez", "thales", "safran", "airbus", "renault", "stellantis",
    "michelin", "decathlon", "fnac", "darty", "ikea", "amazon", "la poste",
    "enedis", "grdf", "cstb", "quadient", "berner", "jungheinrich",
    "conforama", "nrj", "canal plus",
]


class CurateError(ValueError):
    pass


def _jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _norm_url(url):
    url = (url or "").strip()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    return url.rstrip("/")


def _match_group(title, groups):
    """Case/accent-insensitive title→role-group match; highest points win."""
    t = " " + jobs.norm(title) + " "
    best = None
    for name, g in groups.items():
        for pat in g["titles"]:
            if f" {jobs.norm(pat)} " in t or jobs.norm(pat) in t:
                if best is None or g["points"] > groups[best]["points"]:
                    best = name
                break
    return best


def run(staging, matrix_path, out, today):
    t0 = time.perf_counter()
    with open(matrix_path, encoding="utf-8") as f:
        matrix = json.load(f)
    offers = _jsonl(os.path.join(staging, "offers.jsonl"))
    companies = _jsonl(os.path.join(staging, "companies.jsonl"))
    if not companies:
        raise CurateError(f"no companies in {staging}/companies.jsonl")

    groups = matrix.get("role_groups") or DEFAULT_ROLE_GROUPS
    exclude_public = matrix.get("exclude_public", True)
    extra_excl = [jobs.norm(x) for x in matrix.get("exclude_employers", [])]
    negative = matrix.get("negative", [])

    offers_by_co = {}
    for o in offers:
        offers_by_co.setdefault(jobs.norm(o.get("company_name")), []).append(o)

    # Measured reachable (SKILL Phase 3): drop criteria this channel/ICP
    # cannot mechanically produce, so 65 % of reachable stays meaningful.
    # VOLUME NEVER GATES: the ≥2-offers bonus rewards a population the SMB
    # target cannot join (field-tested: multi-offer cabinets and mega
    # distributors trusted the committed band while every single-offer
    # target SME plateaued just UNDER the cut and got parked — the sort
    # was inverted). The commit/park decision is therefore computed on a
    # volume-free gate score; volume still boosts the stored hiring_score,
    # where it belongs (a priority signal for rank-accounts downstream).
    with_tool = sum(1 for o in offers if o.get("tool_hits"))
    dropped = ["size (never visible in an ad)",
               "volume (booster only — never gates the cut)"]
    reachable = 75
    if offers and with_tool / len(offers) < 0.05:
        reachable -= 15
        dropped.append(f"tool mention ({with_tool}/{len(offers)} offers)")
    cut = math.ceil(0.65 * reachable)
    park = math.ceil(0.45 * reachable)

    committed, parked, rejected = [], [], []
    for c in companies:
        name = c.get("company_name") or ""
        nname = jobs.norm(name)
        cos = offers_by_co.get(nname, [])
        reason = None

        brand = jobs.agency_suspect(name, "", negative)
        staffing_text = next(
            (o for o in cos if DESC_AGENCY_RE.search(
                jobs.norm((o.get("title", "") or "") + " " + (o.get("description", "") or "")))),
            None)
        if brand:
            reason = f"staffing/cabinet ({brand})"
        elif staffing_text is not None:
            reason = "staffing language in offer text (recruits for a client)"
        elif any(TITLE_CABINET_RE.search(jobs.norm(o.get("title", ""))) for o in cos):
            reason = "expertise-comptable title fingerprint (chef de mission…)"
        elif exclude_public and PUBLIC_RE.search(f" {nname} "):
            reason = "public/nonprofit employer"
        elif any(f" {m} " in f" {nname} " for m in
                 [jobs.norm(m) for m in MEGA_EMPLOYERS] + extra_excl):
            reason = "mega group / excluded employer (>250 evident)"
        elif _match_group(name, groups):
            reason = "employer name is a job title (parsing artifact)"

        role_group = None
        if not reason:
            matched = [(o, _match_group(o.get("title", ""), groups)) for o in cos]
            hits = [(o, g) for o, g in matched if g]
            if not hits:
                reason = "role outside target categories"
            else:
                role_group = max(hits, key=lambda x: groups[x[1]]["points"])[1]

        if reason:
            rejected.append({**c, "reject_reason": reason})
            continue

        role_offers = [o for o, g in hits if g == role_group]
        roles = sorted({o.get("title", "").strip() for o in role_offers if o.get("title")})
        vol = c.get("volume_bonus", 0) or 0
        gate_score = min(100, max(0, c.get("prescore65", 0) - vol)
                         + groups[role_group]["points"])
        score = min(100, c.get("prescore65", 0) + groups[role_group]["points"])
        best = max(role_offers,
                   key=lambda o: (o.get("posted_date") or "", o.get("prescore65", 0)))
        pains = sorted(c.get("pain_hits") or [])
        pains_clause = f" — l'annonce évoque {', '.join(pains)}" if pains else ""
        angle = groups[role_group]["angle"].format(
            roles=", ".join(roles) or role_group, pains=pains_clause,
            n=len(role_offers))
        freshest = c.get("freshest") or best.get("posted_date")
        fresh_days = None
        if freshest:
            try:
                fresh_days = (today - dt.date.fromisoformat(freshest[:10])).days
            except ValueError:
                pass
        row = {
            "name": name, "location": best.get("location", ""),
            "role_group": role_group, "roles": roles,
            "n_role_offers": len(role_offers),
            "hiring_score": score, "gate_score": gate_score,
            "hiring_angle": angle,
            "signal_date": freshest,
            "signal_freshness": "fresh" if fresh_days is not None and fresh_days <= 60
                                else "context",
            "signal_summary": (f"Recrute : {', '.join(roles)}"
                               + (f" — pains : {', '.join(pains)}" if pains else "")
                               + (f" ({len(role_offers)} offres)" if len(role_offers) > 1 else "")),
            "evidence_url": best.get("url", ""),
            "pain_hits": pains, "tool_hits": sorted(c.get("tool_hits") or []),
        }
        (committed if gate_score >= cut else parked if gate_score >= park
         else rejected).append(row if gate_score >= park else
                               {**row, "reject_reason": f"gate score {gate_score} < park {park}"})

    committed.sort(key=lambda r: -r["hiring_score"])
    parked.sort(key=lambda r: -r["hiring_score"])

    os.makedirs(out, exist_ok=True)
    for fname, rows in [("committed.jsonl", committed), ("parked.jsonl", parked),
                        ("rejected.jsonl", rejected)]:
        with open(os.path.join(out, fname), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    payload = [{"name": r["name"], "source": "hiring-signal", "status": "new",
                "location": r["location"], "hiring_score": r["hiring_score"],
                "hiring_angle": r["hiring_angle"]} for r in committed]
    with open(os.path.join(out, "companies_payload.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    reasons = {}
    for r in rejected:
        key = r.get("reject_reason", "?").split("(")[0].strip()
        reasons[key] = reasons.get(key, 0) + 1
    return {
        "ok": True, "companiesIn": len(companies),
        "committed": len(committed), "parked": len(parked),
        "rejected": len(rejected), "rejectReasons": reasons,
        "reachable": reachable, "cut": cut, "parkFloor": park,
        "droppedCriteria": dropped, "out": out,
        "samples": [{"name": r["name"], "score": r["hiring_score"],
                     "signal": r["signal_summary"]} for r in committed[:3]],
        "elapsed_s": round(time.perf_counter() - t0, 3),
    }


def emit_signals(committed_path, ids_path, out, today):
    t0 = time.perf_counter()
    committed = _jsonl(committed_path)
    with open(ids_path, encoding="utf-8") as f:
        sel = json.load(f)
    rows = sel.get("rows", sel) if isinstance(sel, dict) else sel
    ids = {jobs.norm(r.get("name")): r.get("_id") for r in rows if r.get("name")}

    signals, unmatched = [], []
    for c in committed:
        cid = ids.get(jobs.norm(c["name"]))
        if cid is None:
            unmatched.append(c["name"])
            continue
        signals.append({
            "company_id": cid, "company_name": c["name"], "kind": "hiring",
            "date": c.get("signal_date") or "",
            "freshness": c.get("signal_freshness", "context"),
            "summary": c.get("signal_summary", ""),
            "evidence_url": c.get("evidence_url", ""),
            "source": "jobs-board",
            "sig_key": f"hiring:{cid}:{_norm_url(c.get('evidence_url'))}",
            "status": "new", "detected_at": today.isoformat(),
        })
    if unmatched:
        raise CurateError(
            "no _id found for: " + ", ".join(unmatched) +
            " — signals must NEVER be written without company_id; fix the "
            "select (db.py select companies --cols _id,name) and re-run")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(signals, f, ensure_ascii=False)
    return {"ok": True, "signals": len(signals), "out": out,
            "elapsed_s": round(time.perf_counter() - t0, 3)}


def main(argv=None):
    p = argparse.ArgumentParser(description="Frozen curation for find-hiring-signal")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--staging", required=True)
    r.add_argument("--matrix", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--today", default=None)
    e = sub.add_parser("emit-signals")
    e.add_argument("--committed", required=True)
    e.add_argument("--ids", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--today", default=None)
    args = p.parse_args(argv)
    try:
        today = (dt.date.fromisoformat(args.today) if args.today
                 else dt.date.today())
        if args.cmd == "run":
            result = run(args.staging, args.matrix, args.out, today)
        else:
            result = emit_signals(args.committed, args.ids, args.out, today)
    except (CurateError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False),
              file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
