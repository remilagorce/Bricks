#!/usr/bin/env python3
"""Deterministic scoring kernel — the pure half of the score skill.

File in → file out. Zero LLM, zero network, zero database: this script
never touches bricks.db (committing scores back is a separate, atomic
step done via db.py, outside this skill). Judgment-based measures are
materialized as columns BEFORE this script runs (materialize.py) — by
the time `apply` executes, scoring is pure arithmetic: same file + same
spec = same output, forever, explainable to a jury.

Spec (JSON) — four rule kinds:

    {
      "rules": [
        {"label": "role_cto", "kind": "conditional", "into": "sc_role",
         "when": {"col": "role", "op": "icontains", "value": "CTO"}, "points": 4},
        {"label": "role_ceo", "kind": "conditional", "into": "sc_role",
         "when": {"col": "role", "op": "icontains", "value": "CEO"}, "points": 6},
        {"label": "size", "kind": "conditional", "into": "sc_size",
         "when": {"col": "employees", "op": "lt", "value": 40}, "points": 5},
        {"label": "margin", "kind": "arithmetic", "into": "sc_margin",
         "add": ["revenue"], "sub": ["costs"]},
        {"label": "innovation", "kind": "measure", "into": "sc_innovation",
         "requires": "innovation_raw", "points_per_unit": 1,
         "gate": {"col": "industry", "op": "icontains", "value": "tech"},
         "rubric": {"input": "description",
                    "scale": {"min": 1, "max": 10},
                    "anchors": {"10": "deep tech fondamentale",
                                "7": "techno proprietaire forte",
                                "4": "innovation d'usage",
                                "1": "innovation produit"},
                    "evidence": true}},
        {"label": "kill_foreign", "kind": "kill",
         "when": {"col": "country", "op": "ne", "value": "FR"},
         "reason": "hors France"}
      ],
      "total_into": "score",
      "tiers": {"into": "tier", "thresholds": {"A": 15, "B": 8}, "default": "C"}
    }

Semantics:
- conditional: several rules may share one `into` — FIRST match in spec
  order wins for that column (exclusive brackets); no match → 0.
- arithmetic / measure: their `into` belongs to exactly one rule.
- measure: gate fails → 0 (row never sent to a judge). Gate passes but
  the required column is empty → partial score + score_status='missing_input'.
- kill: first matching rule sets killed='true' + kill_reason. The row is
  still scored (it is free); acting on `killed` is the committer's job
  (killed → status='disqualified' happens at commit time, via db.py).
- Conditions: {"col","op","value"} with op in eq ne lt lte gt gte
  contains icontains in regex exists missing — or combinators
  {"all": [...]}, {"any": [...]}, {"not": {...}}.
- Numbers coerce tolerantly: "20-49" → 20, "1 200" → 1200 (first number
  wins). Empty arithmetic inputs count as 0.
- `into` / `requires` names must not start with "_" (reserved by db.py).

CLI (JSON receipt on stdout; on error JSON on stderr + exit 1):
    python3 score.py check <rows.jsonl> <spec.json>
    python3 score.py apply <rows.jsonl> <spec.json> [-o scored.jsonl]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

KINDS = {"conditional", "arithmetic", "measure", "kill"}
OPS = {"eq", "ne", "lt", "lte", "gt", "gte", "contains", "icontains",
       "in", "regex", "exists", "missing"}


class ScoreError(ValueError):
    """Invalid spec or rows — nothing is written."""


# --------------------------------------------------------------------------
# Coercion & conditions
# --------------------------------------------------------------------------

_NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def _num(value):
    """Tolerant numeric coercion; None when no number can be read."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).replace("\u00a0", " ").strip()
    if not s:
        return None
    s = re.sub(r"(?<=\d)[ \u202f](?=\d)", "", s)
    try:
        return float(s.replace(",", "."))
    except ValueError:
        m = _NUM_RE.search(s)
        return float(m.group(0).replace(",", ".")) if m else None


def _exists(cell) -> bool:
    return cell is not None and str(cell).strip() != ""


def eval_cond(cond, row) -> bool:
    """Evaluate a condition object against a row. Safe: no eval, no SQL."""
    if not isinstance(cond, dict):
        raise ScoreError(f"condition must be an object, got {cond!r}")
    if "all" in cond:
        return all(eval_cond(c, row) for c in cond["all"])
    if "any" in cond:
        return any(eval_cond(c, row) for c in cond["any"])
    if "not" in cond:
        return not eval_cond(cond["not"], row)

    col, op = cond.get("col"), cond.get("op")
    if not col or op not in OPS:
        raise ScoreError(f"condition needs col + op in {sorted(OPS)}: {cond!r}")
    cell = row.get(col)

    if op == "exists":
        return _exists(cell)
    if op == "missing":
        return not _exists(cell)

    value = cond.get("value")
    if op in ("lt", "lte", "gt", "gte"):
        a, b = _num(cell), _num(value)
        if a is None or b is None:
            return False
        return {"lt": a < b, "lte": a <= b, "gt": a > b, "gte": a >= b}[op]
    if op in ("eq", "ne"):
        a, b = _num(cell), _num(value)
        if a is not None and b is not None:
            same = a == b
        else:
            same = str(cell or "").strip().casefold() == str(value or "").strip().casefold()
        return same if op == "eq" else not same
    if op == "contains":
        return _exists(cell) and str(value) in str(cell)
    if op == "icontains":
        return _exists(cell) and str(value).casefold() in str(cell).casefold()
    if op == "in":
        if not isinstance(value, list):
            raise ScoreError(f"op 'in' needs a list value: {cond!r}")
        return str(cell or "").strip().casefold() in {str(v).strip().casefold() for v in value}
    if op == "regex":
        return _exists(cell) and re.search(str(value), str(cell)) is not None
    raise ScoreError(f"unhandled op {op!r}")


def _cond_cols(cond) -> list:
    if "all" in cond:
        return [c for sub in cond["all"] for c in _cond_cols(sub)]
    if "any" in cond:
        return [c for sub in cond["any"] for c in _cond_cols(sub)]
    if "not" in cond:
        return _cond_cols(cond["not"])
    return [cond["col"]] if cond.get("col") else []


# --------------------------------------------------------------------------
# Spec
# --------------------------------------------------------------------------

def load_spec(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        spec = json.load(f)
    rules = spec.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ScoreError("spec.rules must be a non-empty list")
    labels, exclusive_intos = set(), set()
    for r in rules:
        label, kind = r.get("label"), r.get("kind")
        if not label or label in labels:
            raise ScoreError(f"every rule needs a unique label: {r!r}")
        labels.add(label)
        if kind not in KINDS:
            raise ScoreError(f"rule {label!r}: kind must be one of {sorted(KINDS)}")
        if kind != "kill":
            into = r.get("into")
            if not into or into.startswith("_"):
                raise ScoreError(f"rule {label!r}: needs an 'into' column not starting with _")
            if kind in ("arithmetic", "measure"):
                if into in exclusive_intos:
                    raise ScoreError(f"rule {label!r}: into {into!r} already used by another "
                                     "arithmetic/measure rule")
                exclusive_intos.add(into)
        if kind in ("conditional", "kill"):
            if "when" not in r:
                raise ScoreError(f"rule {label!r}: needs a 'when' condition")
            _cond_cols(r["when"])  # validates shape
        if kind == "conditional" and not isinstance(r.get("points"), (int, float)):
            raise ScoreError(f"rule {label!r}: conditional needs numeric 'points'")
        if kind == "arithmetic" and not (r.get("add") or r.get("sub")):
            raise ScoreError(f"rule {label!r}: arithmetic needs 'add' and/or 'sub' column lists")
        if kind == "measure":
            req = r.get("requires")
            if not req or req.startswith("_"):
                raise ScoreError(f"rule {label!r}: measure needs a 'requires' column "
                                 "not starting with _")
            rubric = r.get("rubric")
            if not isinstance(rubric, dict) or not rubric.get("input") \
                    or not isinstance(rubric.get("scale"), dict):
                raise ScoreError(f"rule {label!r}: measure needs rubric.input + rubric.scale")
    total_into = spec.get("total_into", "score")
    if total_into.startswith("_"):
        raise ScoreError("total_into must not start with _")
    spec["total_into"] = total_into
    return spec


# --------------------------------------------------------------------------
# Rows IO
# --------------------------------------------------------------------------

def load_rows(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ScoreError(f"{path}:{n}: invalid JSON line ({exc})") from None
            if not isinstance(obj, dict):
                raise ScoreError(f"{path}:{n}: each line must be a JSON object")
            rows.append(obj)
    if not rows:
        raise ScoreError(f"no rows in {path}")
    return rows


def write_rows(path: str, rows: list) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


# --------------------------------------------------------------------------
# Apply
# --------------------------------------------------------------------------

def _intify(x: float):
    return int(x) if float(x).is_integer() else x


def measure_gate_open(rule: dict, row: dict) -> bool:
    gate = rule.get("gate")
    return gate is None or eval_cond(gate, row)


def score_row(row: dict, spec: dict) -> dict:
    out = dict(row)
    status = "done"
    written = set()
    conditional_intos, all_intos = [], []

    for rule in spec["rules"]:
        kind = rule["kind"]
        if kind == "kill":
            if "killed" not in out and eval_cond(rule["when"], row):
                out["killed"] = "true"
                out["kill_reason"] = rule.get("reason", rule["label"])
            continue
        into = rule["into"]
        if into not in all_intos:
            all_intos.append(into)
        if kind == "conditional":
            if into not in conditional_intos:
                conditional_intos.append(into)
            if into in written:
                continue
            if eval_cond(rule["when"], row):
                out[into] = _intify(rule["points"])
                written.add(into)
        elif kind == "arithmetic":
            total = 0.0
            for c in rule.get("add", []):
                total += _num(row.get(c)) or 0.0
            for c in rule.get("sub", []):
                total -= _num(row.get(c)) or 0.0
            out[into] = _intify(total)
        elif kind == "measure":
            if not measure_gate_open(rule, row):
                out[into] = 0
            else:
                raw = _num(row.get(rule["requires"]))
                if raw is None:
                    out[into] = None
                    status = "missing_input"
                else:
                    out[into] = _intify(raw * rule.get("points_per_unit", 1))

    for into in conditional_intos:
        if into not in written and out.get(into) is None:
            out[into] = 0

    total = sum(v for c in all_intos if (v := _num(out.get(c))) is not None)
    out[spec["total_into"]] = _intify(total)

    tiers = spec.get("tiers")
    if tiers:
        tier = tiers.get("default", "C")
        for name, threshold in sorted(tiers["thresholds"].items(),
                                      key=lambda kv: -float(kv[1])):
            if total >= float(threshold):
                tier = name
                break
        out[tiers.get("into", "tier")] = tier

    out["score_status"] = status
    return out


def apply_rows(rows: list, spec: dict) -> list:
    return [score_row(r, spec) for r in rows]


# --------------------------------------------------------------------------
# Check
# --------------------------------------------------------------------------

def check(rows: list, spec: dict) -> dict:
    present = set()
    for r in rows:
        present.update(r.keys())

    hard_refs = []
    for rule in spec["rules"]:
        kind = rule["kind"]
        if kind in ("conditional", "kill"):
            hard_refs += _cond_cols(rule["when"])
        elif kind == "arithmetic":
            hard_refs += list(rule.get("add", [])) + list(rule.get("sub", []))
        elif kind == "measure":
            if rule.get("gate"):
                hard_refs += _cond_cols(rule["gate"])
            inputs = rule["rubric"]["input"]
            hard_refs += inputs if isinstance(inputs, list) else [inputs]
    hard_missing = sorted(set(hard_refs) - present)

    measures = []
    for rule in spec["rules"]:
        if rule["kind"] != "measure":
            continue
        needing = []
        for i, row in enumerate(rows, 1):
            if measure_gate_open(rule, row) and _num(row.get(rule["requires"])) is None:
                needing.append(row.get("rid", i))
        measures.append({"label": rule["label"], "requires": rule["requires"],
                         "rowsNeedingJudgment": len(needing), "rids": needing[:200]})

    return {"ok": not hard_missing, "rows": len(rows),
            "hardMissingColumns": hard_missing, "measures": measures}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic scoring: file + spec in, scored file out.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check", help="validate the spec against the rows; report gaps")
    p.add_argument("rows")
    p.add_argument("spec")

    p = sub.add_parser("apply", help="score every row; write scored JSONL")
    p.add_argument("rows")
    p.add_argument("spec")
    p.add_argument("-o", "--out", default=None,
                   help="output path (default: scored.jsonl next to the input)")

    args = parser.parse_args(argv)
    try:
        spec = load_spec(args.spec)
        rows = load_rows(args.rows)
        if args.command == "check":
            result = check(rows, spec)
        else:
            scored = apply_rows(rows, spec)
            out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.rows)),
                                           "scored.jsonl")
            write_rows(out, scored)
            killed = sum(1 for r in scored if r.get("killed") == "true")
            missing = sum(1 for r in scored if r["score_status"] == "missing_input")
            totals = [_num(r.get(spec["total_into"])) or 0 for r in scored]
            result = {"ok": True, "action": "apply", "rows": len(scored), "out": out,
                      "killed": killed, "missingInput": missing,
                      "scoreMin": _intify(min(totals)), "scoreMax": _intify(max(totals))}
    except (ScoreError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False),
              file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
