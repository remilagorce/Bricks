#!/usr/bin/env python3
"""Materialize judgment measures, then stream rows into the scoring kernel.

The impure half of the score skill — the ONLY place where a model is
consulted, quarantined before the deterministic pass. For every `measure`
rule in the spec, rows that pass the gate but lack the required column
are judged in parallel batches through `tools/core/agent.py` — the single
AI door of the project — with a JSON schema guaranteeing the answer
shape, against the rubric VERBATIM. Everything downstream is score.py,
pure.

Streaming: nobody waits for the whole table. Rows that need no judgment
are scored and appended to scored.jsonl immediately; each judged batch is
scored the moment its last judgment lands. scored.jsonl fills up
progressively, in completion order — row order in the file does not matter.

Never pay twice: every judgment is appended to judgments.jsonl
(checkpoint, keyed rid+rule) as soon as it is validated. An interrupted
run resumes from the checkpoint and only judges the gaps. scored.jsonl,
by contrast, is rebuilt on every run — scoring is free.

This script never touches bricks.db. Committing scores back to a
workspace is a separate, atomic step (db.py), outside this skill.

CLI (summary JSON on stdout, progress on stderr):
    python3 materialize.py run <work.jsonl> <spec.json>
        [--dir RUNDIR] [--batch 6] [--workers 4] [--dry-run]

The judge is agent.agent() — subscription by default, `haiku` model
(override with BRICKS_JUDGE_MODEL). BRICKS_AGENT_TRANSPORT=api applies
here too (machines where the SDK stack cannot run).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score as kernel  # noqa: E402

_CORE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", "..", "tools", "core"))
sys.path.insert(0, _CORE)

JUDGE_TIMEOUT = 300
JUDGE_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["judgments"],
    "properties": {"judgments": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["rid", "value", "evidence"],
        "properties": {"rid": {"type": "integer"},
                       "value": {"anyOf": [{"type": "integer"},
                                           {"type": "null"}]},
                       "evidence": {"type": "string"}}}}},
}


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------
# Judge call
# --------------------------------------------------------------------------

def build_prompt(rule: dict, batch: list) -> str:
    rubric = rule["rubric"]
    scale = rubric["scale"]
    inputs = rubric["input"]
    if isinstance(inputs, str):
        inputs = [inputs]
    anchors = "\n".join(f"  {k}: {v}" for k, v in
                        sorted(rubric.get("anchors", {}).items(),
                               key=lambda kv: -kernel._num(kv[0])))
    wants_evidence = rubric.get("evidence", True)
    payload = [{"rid": r["rid"], **{c: r.get(c, "") for c in inputs}} for r in batch]

    lines = [
        "You are a deterministic scoring judge. Apply the rubric below EXACTLY",
        "as written — no personal interpretation beyond the anchors.",
        "",
        f"Measure: {rule['label']}",
        f"Scale: integer from {scale['min']} to {scale['max']}.",
        "Anchors (interpolate between them):",
        anchors or "  (none)",
        "",
        f"Judge each row from its field(s): {', '.join(inputs)}.",
        "If the field is empty or genuinely unjudgeable, use value null.",
    ]
    if wants_evidence:
        lines.append("For every row, 'evidence' must be a short verbatim quote from the "
                     "input that justifies the value (empty string when value is null).")
    lines += [
        "",
        "Rows (JSON):",
        json.dumps(payload, ensure_ascii=False),
        "",
        "Answer with one judgment object per input row.",
    ]
    return "\n".join(lines)


def validate_judgments(rule: dict, batch: list, answers: list) -> dict:
    """Return {rid: {value, evidence}} or raise on any invalid answer."""
    scale = rule["rubric"]["scale"]
    lo, hi = float(scale["min"]), float(scale["max"])
    wants_evidence = rule["rubric"].get("evidence", True)
    expected = {r["rid"] for r in batch}
    out = {}
    for a in answers:
        if not isinstance(a, dict) or a.get("rid") not in expected:
            raise ValueError(f"unexpected answer object: {a!r}")
        rid, value = a["rid"], a.get("value")
        if value is not None:
            v = kernel._num(value)
            if v is None or not (lo <= v <= hi):
                raise ValueError(f"rid {rid}: value {value!r} outside [{lo}, {hi}]")
            value = kernel._intify(v)
            if wants_evidence and not str(a.get("evidence") or "").strip():
                raise ValueError(f"rid {rid}: judged value without evidence")
        out[rid] = {"value": value, "evidence": str(a.get("evidence") or "").strip()}
    missing = expected - set(out)
    if missing:
        raise ValueError(f"judge skipped rids {sorted(missing)}")
    return out


def judge_batch(rule: dict, batch: list) -> dict:
    """Call the judge once (agent.py, schema-guaranteed), retry once."""
    import agent as agentmod
    prompt = build_prompt(rule, batch)
    model = os.environ.get("BRICKS_JUDGE_MODEL", "").strip() or "haiku"
    last_error = None
    for attempt in (1, 2):
        try:
            out = agentmod.agent(prompt, schema=JUDGE_SCHEMA, model=model,
                                 timeout=JUDGE_TIMEOUT)
            return validate_judgments(rule, batch, out.get("judgments", []))
        except (ValueError, agentmod.AgentError) as exc:
            last_error = exc
            log(f"[judge] {rule['label']}: attempt {attempt} failed ({exc})")
    raise ValueError(f"batch failed after retry: {last_error}")


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

def evidence_col(rule: dict) -> str:
    return rule["rubric"].get("evidence_into", f"{rule['label']}_evidence")


def load_checkpoint(path: str) -> dict:
    done = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    j = json.loads(line)
                    done[(j["rid"], j["rule"])] = j
    return done


def run(work_path: str, spec_path: str, rundir: str, batch_size: int,
        workers: int, dry_run: bool) -> dict:
    spec = kernel.load_spec(spec_path)
    rows = kernel.load_rows(work_path)

    # Stable rids: checkpoints and streaming both key on them.
    next_rid = max((r["rid"] for r in rows if isinstance(r.get("rid"), int)), default=0)
    for r in rows:
        if not isinstance(r.get("rid"), int):
            next_rid += 1
            r["rid"] = next_rid
    kernel.write_rows(work_path, rows)
    by_rid = {r["rid"]: r for r in rows}

    gaps = kernel.check(rows, spec)
    if gaps["hardMissingColumns"]:
        raise kernel.ScoreError(
            f"columns referenced by the spec are absent from the rows: "
            f"{gaps['hardMissingColumns']} — fix the spec or the intake first")

    checkpoint_path = os.path.join(rundir, "judgments.jsonl")
    scored_path = os.path.join(rundir, "scored.jsonl")
    checkpoint = load_checkpoint(checkpoint_path)

    measure_rules = [r for r in spec["rules"] if r["kind"] == "measure"]
    tasks, pending, restored = [], {}, 0
    for rule in measure_rules:
        todo = []
        for row in rows:
            if not kernel.measure_gate_open(rule, row):
                continue
            if kernel._num(row.get(rule["requires"])) is not None:
                continue
            saved = checkpoint.get((row["rid"], rule["label"]))
            if saved is not None:
                if saved["value"] is not None:
                    row[rule["requires"]] = saved["value"]
                    row[evidence_col(rule)] = saved["evidence"]
                restored += 1
                continue
            todo.append(row)
            pending[row["rid"]] = pending.get(row["rid"], 0) + 1
        for i in range(0, len(todo), batch_size):
            tasks.append((rule, todo[i:i + batch_size]))

    if dry_run:
        return {"ok": True, "action": "dry-run", "rows": len(rows),
                "judgeCalls": len(tasks),
                "rowsToJudge": len(pending), "fromCheckpoint": restored,
                "perRule": {r["label"]: sum(len(b) for rl, b in tasks if rl is r)
                            for r in measure_rules}}

    lock = threading.Lock()
    scored_count = failed_rows = 0
    failures = []

    # scored.jsonl is rebuilt every run — judgments are the only paid state.
    open(scored_path, "w", encoding="utf-8").close()

    def score_and_append(batch_rows: list) -> None:
        nonlocal scored_count
        scored = kernel.apply_rows(batch_rows, spec)
        with open(scored_path, "a", encoding="utf-8") as f:
            for s in scored:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        scored_count += len(scored)
        log(f"[score] {scored_count}/{len(rows)} rows scored")

    ready = [r for r in rows if r["rid"] not in pending]
    if ready:
        score_and_append(ready)

    def on_batch_done(rule: dict, batch: list, judgments: dict | None) -> None:
        """Merge one batch's judgments; stream rows whose last gap just closed."""
        nonlocal failed_rows
        releasable = []
        with lock:
            for row in batch:
                rid = row["rid"]
                if judgments is not None:
                    j = judgments[rid]
                    if j["value"] is not None:
                        row[rule["requires"]] = j["value"]
                        row[evidence_col(rule)] = j["evidence"]
                    with open(checkpoint_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({"rid": rid, "rule": rule["label"], **j},
                                           ensure_ascii=False) + "\n")
                else:
                    failed_rows += 1
                pending[rid] -= 1
                if pending[rid] == 0:
                    releasable.append(by_rid[rid])
            if releasable:
                score_and_append(releasable)

    if tasks:
        log(f"[judge] {len(tasks)} calls to run ({sum(len(b) for _, b in tasks)} row-judgments, "
            f"{restored} restored from checkpoint)")
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(judge_batch, rule, batch): (rule, batch)
                       for rule, batch in tasks}
            for fut in concurrent.futures.as_completed(futures):
                rule, batch = futures[fut]
                try:
                    judgments = fut.result()
                except ValueError as exc:
                    failures.append({"rule": rule["label"],
                                     "rids": [r["rid"] for r in batch],
                                     "error": str(exc)})
                    judgments = None
                on_batch_done(rule, batch, judgments)

    kernel.write_rows(work_path, rows)  # persist materialized columns

    scored_rows = kernel.load_rows(scored_path)
    totals = [kernel._num(r.get(spec["total_into"])) or 0 for r in scored_rows]
    return {"ok": not failures, "action": "run", "rows": len(rows),
            "scored": len(scored_rows), "out": scored_path,
            "judgeCalls": len(tasks), "fromCheckpoint": restored,
            "failedRows": failed_rows, "failures": failures,
            "killed": sum(1 for r in scored_rows if r.get("killed") == "true"),
            "missingInput": sum(1 for r in scored_rows
                                if r.get("score_status") == "missing_input"),
            "scoreMin": kernel._intify(min(totals)) if totals else None,
            "scoreMax": kernel._intify(max(totals)) if totals else None}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Judge missing measures (headless agents), stream rows into score.py.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("run", help="materialize judgments then score, streaming")
    p.add_argument("rows", help="working JSONL file (rewritten in place with rid + judged columns)")
    p.add_argument("spec", help="spec.json")
    p.add_argument("--dir", default=None, help="run dir for judgments.jsonl / scored.jsonl "
                                               "(default: the rows file's directory)")
    p.add_argument("--batch", type=int, default=6, help="rows per judge call (default 6)")
    p.add_argument("--workers", type=int, default=4, help="parallel judge calls (default 4)")
    p.add_argument("--dry-run", action="store_true",
                   help="report how many judge calls would run, judge nothing")

    args = parser.parse_args(argv)
    rundir = args.dir or os.path.dirname(os.path.abspath(args.rows))
    os.makedirs(rundir, exist_ok=True)
    try:
        result = run(args.rows, args.spec, rundir, args.batch, args.workers, args.dry_run)
    except (kernel.ScoreError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False),
              file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
