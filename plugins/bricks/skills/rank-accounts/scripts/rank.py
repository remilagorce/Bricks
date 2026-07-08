#!/usr/bin/env python3
"""Account prioritization kernel — the frozen, deterministic half of rank-accounts.

File in → file out. Zero LLM, zero network, zero database: like score.py and
the fetch engines, this script never touches bricks.db (reading the rows and
committing the results are separate db.py steps, done by the skill). Given the
same inputs and the same spec it produces the same output, forever — a
priority ranking must be reproducible and explainable to a jury, never
re-invented by a model each run.

What it does, in one deterministic pass (a plain for-loop over companies):
  1. aggregate each company's `signals` rows into features (strongest signal,
     freshness, volume);
  2. fuse ICP fit (`tier`) + the strongest fresh signal + a volume bonus into
     `priority_score` /100 and a readable `priority_tier` (now / week / nurture);
  3. assemble a `why_now` one-liner from the strongest signal (template, no
     model) + its `why_now_url`.
The weights and thresholds are NOT in the code — they live in the spec JSON
(the "holes"), editable by hand or by the skill ("mets hiring à 40").

Inputs are whatever `db.py select` prints (a dict with a "rows" list), or a
plain JSON array, or JSONL — all three are accepted for companies and signals.

CLI (JSON receipt on stdout; on error JSON on stderr + exit 1):
    python3 rank.py run --companies companies.json --signals signals.json \
        --spec rank_spec.json [--out updates.json] [--tier-col tier] \
        [--today YYYY-MM-DD]

Output `updates.json` is a JSON array ready for `db.py modify --updates -`:
each object is `{"_id": <id>, "priority_score": .., "priority_tier": "..",
"why_now": "..", "why_now_url": ".."}`.

Spec (JSON) — every field has a default baked in, so an empty `{}` still runs:

    {
      "fit":   {"tier_col": "tier",
                "tier_points": {"A": 40, "B": 25, "C": 10},
                "default_points": 10},
      "signal_kind_points": {"hiring": 30, "intent": 30, "job_change": 20,
                             "company_news": 15, "new_post": 10},
      "recency_multiplier": [[7, 1.0], [30, 0.8], [60, 0.6]],
      "context_multiplier": 0.2,
      "freshness_label_multiplier": {"fresh": 0.8, "context": 0.2},
      "volume_bonus": {"min_fresh_kinds": 2, "min_fresh_signals": 2, "points": 10},
      "warning": {"field": "warning", "cap_score": 15},
      "tiers": {"now": 70, "week": 40, "default": "nurture"},
      "kind_labels": {"hiring": "Recrute en ce moment",
                      "intent": "Signal d'intention",
                      "job_change": "Changement de poste récent",
                      "company_news": "Actu entreprise",
                      "new_post": "Publication LinkedIn récente"},
      "columns": {"company_id": "_id", "name": "name",
                  "priority_score": "priority_score",
                  "priority_tier": "priority_tier",
                  "why_now": "why_now", "why_now_url": "why_now_url"},
      "signals": {"company_id": "company_id", "kind": "kind",
                  "freshness": "freshness", "date": "date",
                  "summary": "summary", "evidence_url": "evidence_url"}
    }
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time

DEFAULT_SPEC = {
    "fit": {"tier_col": "tier",
            "tier_points": {"A": 40, "B": 25, "C": 10},
            "default_points": 10},
    "signal_kind_points": {"hiring": 30, "intent": 30, "job_change": 20,
                           "company_news": 15, "new_post": 10},
    "recency_multiplier": [[7, 1.0], [30, 0.8], [60, 0.6]],
    "context_multiplier": 0.2,
    "freshness_label_multiplier": {"fresh": 0.8, "context": 0.2},
    "volume_bonus": {"min_fresh_kinds": 2, "min_fresh_signals": 2, "points": 10},
    "warning": {"field": "warning", "cap_score": 15},
    "tiers": {"now": 70, "week": 40, "default": "nurture"},
    "kind_labels": {"hiring": "Recrute en ce moment",
                    "intent": "Signal d'intention",
                    "job_change": "Changement de poste récent",
                    "company_news": "Actu entreprise",
                    "new_post": "Publication LinkedIn récente"},
    "columns": {"company_id": "_id", "name": "name",
                "priority_score": "priority_score",
                "priority_tier": "priority_tier",
                "why_now": "why_now", "why_now_url": "why_now_url"},
    "signals": {"company_id": "company_id", "company_name": "company_name",
                "kind": "kind", "freshness": "freshness", "date": "date",
                "summary": "summary", "evidence_url": "evidence_url"},
}


class RankError(ValueError):
    """Raised on any invalid input; nothing is written."""


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def _load_rows(path: str, what: str) -> list[dict]:
    """Accept a db.py select payload (dict with 'rows'), a JSON array, or JSONL."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read().strip()
    except OSError as exc:
        raise RankError(f"cannot read {what} file {path!r}: {exc}") from None
    if not text:
        return []
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        rows = []
        for i, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise RankError(f"{what}: line {i} is not valid JSON ({exc})") from None
        return rows
    if isinstance(obj, dict) and isinstance(obj.get("rows"), list):
        return obj["rows"]
    if isinstance(obj, list):
        return obj
    raise RankError(f"{what}: expected a db.py select payload, a JSON array, or JSONL")


def _merge_spec(user: dict) -> dict:
    """Shallow-merge the user spec onto the defaults (one level for nested dicts)."""
    spec = json.loads(json.dumps(DEFAULT_SPEC))  # deep copy
    for key, value in (user or {}).items():
        if isinstance(value, dict) and isinstance(spec.get(key), dict):
            spec[key].update(value)
        else:
            spec[key] = value
    return spec


# --------------------------------------------------------------------------
# Deterministic scoring helpers
# --------------------------------------------------------------------------

_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _norm_name(value) -> str:
    """Loose company-name key for the defensive company_id fallback."""
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().lower().split())


def _parse_date(value) -> dt.date | None:
    if not isinstance(value, str):
        return None
    m = _DATE_RE.search(value)
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _fit_points(company: dict, spec: dict, tier_col: str) -> int:
    tier = str(company.get(tier_col) or "").strip().upper()
    points = spec["fit"]["tier_points"]
    if tier in points:
        return points[tier]
    for key, pts in points.items():                       # tolerate "🟢 A"
        if key.upper() in tier:
            return pts
    return spec["fit"]["default_points"]


def _signal_multiplier(sig: dict, spec: dict, cols: dict, today: dt.date) -> float:
    """A signal's freshness weight: by real age if a date is present, else by label."""
    date = _parse_date(sig.get(cols["date"]))
    if date is not None:
        age = (today - date).days
        for max_days, mult in sorted(spec["recency_multiplier"]):
            if age <= max_days:
                return float(mult)
        return float(spec["context_multiplier"])
    label = str(sig.get(cols["freshness"]) or "").strip().lower()
    return float(spec["freshness_label_multiplier"].get(label, spec["context_multiplier"]))


def _rank_company(company: dict, sigs: list[dict], spec: dict,
                  tier_col: str, today: dt.date) -> dict:
    ccols, scols = spec["columns"], spec["signals"]
    kind_points = spec["signal_kind_points"]

    fit_pts = _fit_points(company, spec, tier_col)

    context_mult = spec["context_multiplier"]
    top = None                       # strongest overall (drives the score)
    top_fresh = None                 # strongest FRESH one (drives why_now)
    fresh_kinds: set[str] = set()
    fresh_count = 0
    warned = False
    warn_field = spec.get("warning", {}).get("field")
    for sig in sigs:
        kind = str(sig.get(scols["kind"]) or "").strip()
        base = kind_points.get(kind, 0)
        mult = _signal_multiplier(sig, spec, scols, today)
        effective = base * mult
        is_fresh = base and mult > context_mult
        if is_fresh:
            fresh_kinds.add(kind)
            fresh_count += 1
        if base and (top is None or effective > top[0]):
            top = (effective, sig, mult, kind)
        if is_fresh and (top_fresh is None or effective > top_fresh[0]):
            top_fresh = (effective, sig, mult, kind)
        if warn_field and str(sig.get(warn_field) or "").strip().lower() in ("1", "true", "yes"):
            warned = True

    signal_pts = top[0] if top else 0.0
    # Volume = strength: fires on signal DIVERSITY (≥2 fresh kinds) OR on
    # same-kind VOLUME (≥2 fresh signals, e.g. 3 job offers ≤60 days —
    # find-hiring-signal doctrine: several offers = stronger signal;
    # field-tested: 3 fresh hiring offers earned nothing vs a single one).
    volume = spec["volume_bonus"]
    volume_pts = volume["points"] if (
        len(fresh_kinds) >= volume["min_fresh_kinds"]
        or fresh_count >= volume.get("min_fresh_signals", 2)) else 0

    score = fit_pts + signal_pts + volume_pts
    if warned:
        score = min(score, spec["warning"]["cap_score"])
    score = int(round(min(100.0, max(0.0, score))))

    tiers = spec["tiers"]
    if score >= tiers["now"]:
        band = "now"
    elif score >= tiers["week"]:
        band = "week"
    else:
        band = tiers["default"]

    # why_now answers "why call NOW" — so it is built ONLY from a FRESH
    # signal. A context-only account (stale/undated signal, e.g. a mere
    # active careers page) gets an empty why_now, never "Recrute en ce
    # moment" (field-tested overstatement): its score reflects the weak
    # context contribution, and write-outreach falls back to the pain point.
    why_now, why_url = "", ""
    if top_fresh is not None:
        sig = top_fresh[1]
        label = spec["kind_labels"].get(top_fresh[3], top_fresh[3])
        summary = str(sig.get(scols["summary"]) or "").strip()
        why_now = f"{label} : {summary}" if summary else label
        why_url = str(sig.get(scols["evidence_url"]) or "").strip()

    return {
        "_id": company.get(ccols["company_id"]),
        ccols["priority_score"]: score,
        ccols["priority_tier"]: band,
        ccols["why_now"]: why_now,
        ccols["why_now_url"]: why_url,
    }


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

def run(companies_path: str, signals_path: str, spec_path: str | None,
        out_path: str, tier_col: str | None, today: dt.date) -> dict:
    user_spec = {}
    if spec_path:
        try:
            with open(spec_path, encoding="utf-8") as f:
                user_spec = json.load(f)
        except OSError as exc:
            raise RankError(f"cannot read spec {spec_path!r}: {exc}") from None
        except json.JSONDecodeError as exc:
            raise RankError(f"spec {spec_path!r} is not valid JSON ({exc})") from None
    spec = _merge_spec(user_spec)
    resolved_tier_col = tier_col or spec["fit"]["tier_col"]

    companies = _load_rows(companies_path, "companies")
    signals = _load_rows(signals_path, "signals")

    id_col = spec["columns"]["company_id"]
    name_col = spec["columns"].get("name", "name")
    sig_id = spec["signals"]["company_id"]
    sig_name = spec["signals"].get("company_name", "company_name")

    # Unambiguous name → id map, for the defensive fallback below.
    name_to_id: dict = {}
    ambiguous: set = set()
    for company in companies:
        cid = company.get(id_col)
        nm = _norm_name(company.get(name_col))
        if cid is None or not nm:
            continue
        if nm in name_to_id and name_to_id[nm] != str(cid):
            ambiguous.add(nm)
        else:
            name_to_id[nm] = str(cid)

    by_company: dict = {}
    linked_by_name = 0
    orphaned = 0
    for sig in signals:
        key = sig.get(sig_id)
        if key is None or str(key).strip() == "":
            # Defensive: a writer that forgot company_id (field-tested —
            # find-hiring-signal orphaned its signals, which silently sank
            # the strongest accounts to no-signal). Recover by unambiguous
            # name match instead of dropping in silence.
            nm = _norm_name(sig.get(sig_name))
            if nm and nm in name_to_id and nm not in ambiguous:
                key = name_to_id[nm]
                linked_by_name += 1
            else:
                orphaned += 1
                continue
        by_company.setdefault(str(key), []).append(sig)

    updates, tier_counts, with_signal = [], {"now": 0, "week": 0, "nurture": 0}, 0
    for company in companies:                                  # the loop
        cid = company.get(id_col)
        if cid is None:
            continue
        sigs = by_company.get(str(cid), [])
        result = _rank_company(company, sigs, spec, resolved_tier_col, today)
        updates.append(result)
        band = result[spec["columns"]["priority_tier"]]
        tier_counts[band] = tier_counts.get(band, 0) + 1
        if result[spec["columns"]["why_now"]]:
            with_signal += 1

    updates.sort(key=lambda u: u.get(spec["columns"]["priority_score"], 0), reverse=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(updates, f, ensure_ascii=False)

    samples = updates[:3]
    return {
        "ok": True,
        "ranked": len(updates),
        "withSignal": with_signal,
        "noSignal": len(updates) - with_signal,
        "tierDistribution": tier_counts,
        "signalsSeen": len(signals),
        "linkedByName": linked_by_name,
        "orphanedSignals": orphaned,
        "out": out_path,
        "tierCol": resolved_tier_col,
        "today": today.isoformat(),
        "samples": samples,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic account prioritization kernel.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("run", help="compute priority_score / priority_tier / why_now")
    p.add_argument("--companies", required=True, help="db.py select payload / JSON array / JSONL")
    p.add_argument("--signals", required=True, help="db.py select payload / JSON array / JSONL")
    p.add_argument("--spec", default=None, help="spec JSON (weights/thresholds); defaults baked in")
    p.add_argument("--out", default="updates.json", help="output JSON array for db.py modify --updates -")
    p.add_argument("--tier-col", default=None, help="fit tier column name (overrides the spec)")
    p.add_argument("--today", default=None, help="YYYY-MM-DD, for reproducible recency (default: today)")

    args = parser.parse_args(argv)
    t0 = time.perf_counter()
    try:
        if args.today:
            m = _DATE_RE.fullmatch(args.today.strip())
            if not m:
                raise RankError("--today must be YYYY-MM-DD")
            today = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        else:
            today = dt.date.today()
        result = run(args.companies, args.signals, args.spec, args.out, args.tier_col, today)
    except RankError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    result["elapsed_s"] = round(time.perf_counter() - t0, 3)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
