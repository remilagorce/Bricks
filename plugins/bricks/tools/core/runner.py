#!/usr/bin/env python3
"""Bricks runner — THE loop. Zero intelligence, total bookkeeping.

Takes a pipeline of steps and a table: for EACH row the steps run
sequentially (step1 then step2...), and the ROWS run in parallel
(ThreadPoolExecutor, hard cap 10 workers).

Step contract (a plain Python function):
    step(row: dict, ctx: dict) -> dict
    # row: the current row (DB columns + fields produced by previous steps, merged)
    # ctx: {"db": path, "table": str, "commit": bool}
    # return: dict of fields to write on the row (merged into row for the next step)
    # an exception -> the row is 'failed' (pipeline stopped for that row only)

Two kinds of steps:
- --step path/to/file.py:fn   a custom importable function (repeatable, in order)
- --ai '{"prompt":"...{{col}}...","schema":{...},"web":true,"model":"haiku"}'
  the built-in AI step: fills {{col}} from the row, calls agent.agent(),
  returns the structured dict (schema properties = columns to write).

THE IRON GATE — preview before any mass write:
- WITHOUT --commit: processes the first 10 eligible rows, prints every
  result, writes NOTHING (not even a status).
- WITH --commit: --status-col is required; each row goes
  running -> steps -> done (or failed + <base>_error). Statuses are the
  checkpoint: re-running the same command resumes the remaining pending rows.

CLI:
    python3 runner.py --table companies [--step f.py:fn]... [--ai '{...}']
        [--status-col email_status] [--where SQL] [--workers 8]
        [--limit N] [--commit] [--db PATH]
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db as dbmod  # noqa: E402

DEFAULT_WORKERS = 8
MAX_WORKERS = 10
PREVIEW_LIMIT = 10
TEMPLATE_RE = re.compile(r"\{\{(\w+)\}\}")


class RunnerError(ValueError):
    """Raised on any invalid run configuration. Nothing is written."""


def load_step(spec: str):
    """Load a step function from 'path/to/file.py:fn' or 'module:fn'."""
    if ":" not in spec:
        raise RunnerError(f"--step expects 'file.py:function' or 'module:function', got {spec!r}")
    target, fn_name = spec.rsplit(":", 1)
    if target.endswith(".py"):
        if not os.path.isfile(target):
            raise RunnerError(f"step file not found: {target}")
        module_spec = importlib.util.spec_from_file_location("bricks_step", target)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
    else:
        module = importlib.import_module(target)
    fn = getattr(module, fn_name, None)
    if not callable(fn):
        raise RunnerError(f"{fn_name!r} is not a function in {target}")
    return fn


def ai_step(params: dict):
    """Build the built-in AI step from {'prompt', 'schema', 'web', 'model', ...}."""
    prompt = (params.get("prompt") or "").strip()
    schema = params.get("schema")
    if not prompt or not isinstance(schema, dict) or not schema.get("properties"):
        raise RunnerError("--ai needs a 'prompt' and a 'schema' with 'properties' "
                          "(properties = the columns to write)")
    import agent as agentmod

    def step(row: dict, ctx: dict) -> dict:
        def fill(match):
            col = match.group(1)
            value = row.get(col)
            if value is None or str(value).strip() == "":
                raise ValueError(f"missing input column {col!r} for this row")
            return str(value)

        merged = TEMPLATE_RE.sub(fill, prompt)
        return agentmod.agent(
            merged, web=bool(params.get("web")), schema=schema,
            model=params.get("model"),
            max_pages=int(params.get("max_pages", agentmod.DEFAULT_MAX_PAGES)),
            timeout=int(params.get("timeout", agentmod.DEFAULT_TIMEOUT)))

    return step


def _eligible_where(status_col: str | None, where: str | None,
                    existing: list[str]) -> str | None:
    parts = []
    if where:
        parts.append(f"({where})")
    if status_col and status_col in existing:
        parts.append(f'("{status_col}" IS NULL OR "{status_col}"=\'pending\')')
    return " AND ".join(parts) or None


def _release_stale(path: str, table: str, status_col: str) -> None:
    """Reset rows left 'running' by a crashed run back to 'pending' — v1 runs
    one commit at a time, so a 'running' row at start can only be stale."""
    stuck = dbmod.select(path, table, where=f"\"{status_col}\"='running'", limit=-1)
    if stuck["rows"]:
        dbmod.modify(path, table,
                     [{"_id": r["_id"], status_col: "pending"} for r in stuck["rows"]])


def _process(row: dict, steps: list, ctx: dict) -> dict:
    """Run the full pipeline on one row; return the merged fields to write."""
    fields: dict = {}
    current = dict(row)
    for step in steps:
        out = step(current, ctx)
        if not isinstance(out, dict):
            raise ValueError(f"step returned {type(out).__name__}, expected dict")
        fields.update(out)
        current.update(out)
    return fields


def run(table: str, steps: list, status_col: str | None = None,
        where: str | None = None, workers: int = DEFAULT_WORKERS,
        limit: int | None = None, commit: bool = False,
        db: str | None = None) -> dict:
    if not steps:
        raise RunnerError("no steps — pass at least one --step or --ai")
    if commit and not status_col:
        raise RunnerError("--commit requires --status-col (the checkpoint column)")
    path = dbmod.resolve(db)
    ctx = {"db": path, "table": table, "commit": commit}
    conn = dbmod.connect(path)
    try:
        existing = dbmod.columns(conn, table)
    finally:
        conn.close()
    if commit and status_col in existing:
        _release_stale(path, table, status_col)
    cond = _eligible_where(status_col, where, existing)

    if not commit:
        effective = min(limit or PREVIEW_LIMIT, PREVIEW_LIMIT)
    else:
        effective = -1 if limit is None else limit
    selected = dbmod.select(path, table, where=cond, limit=effective)
    rows = selected["rows"]
    workers = max(1, min(workers, MAX_WORKERS))

    base = status_col[:-len("_status")] if status_col and status_col.endswith("_status") \
        else (status_col or "")
    error_col = f"{base}_error" if base else None

    results, done, failed = [], 0, 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        def work(row):
            try:
                if commit:
                    dbmod.modify(path, table, [{"_id": row["_id"], status_col: "running"}])
                fields = _process(row, steps, ctx)
                if commit:
                    dbmod.modify(path, table, [{"_id": row["_id"], status_col: "done",
                                                error_col: None, **fields}])
                return {"_id": row["_id"], "fields": fields}
            except Exception as exc:
                if commit:
                    try:
                        dbmod.modify(path, table, [{"_id": row["_id"], status_col: "failed",
                                                    error_col: str(exc)[:300]}])
                    except Exception:
                        pass  # the row stays 'running'; the next run releases it
                return {"_id": row["_id"], "error": str(exc)[:300]}

        futures = [pool.submit(work, row) for row in rows]
        for future in as_completed(futures):
            outcome = future.result()
            results.append(outcome)
            if "error" in outcome:
                failed += 1
            else:
                done += 1

    results.sort(key=lambda r: r["_id"])
    receipt = {"ok": True, "mode": "commit" if commit else "preview",
               "table": table, "eligible": selected["matching"],
               "processed": len(rows), "done": done, "failed": failed}
    if commit:
        receipt["statusCol"] = status_col
    else:
        receipt["written"] = 0
        receipt["results"] = results
    return receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="THE loop: a pipeline of steps per row, rows in parallel. "
                    "Preview by default; --commit writes.")
    parser.add_argument("--table", required=True)
    parser.add_argument("--step", action="append", default=[], metavar="FILE.py:FN",
                        help="custom step function (repeatable, run in order)")
    parser.add_argument("--ai", default=None, metavar="'{JSON}'",
                        help='built-in AI step: {"prompt":"...{{col}}...","schema":{...},'
                             '"web":true,"model":"haiku"}')
    parser.add_argument("--status-col", default=None, help="checkpoint column (X_status)")
    parser.add_argument("--where", default=None, help="extra SQL condition")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--commit", action="store_true",
                        help="claim and WRITE — only after the preview was reviewed")
    parser.add_argument("--db", default=None)
    args = parser.parse_args(argv)
    try:
        steps = [load_step(s) for s in args.step]
        if args.ai:
            try:
                params = json.loads(args.ai)
            except json.JSONDecodeError as exc:
                raise RunnerError(f"--ai: invalid JSON ({exc})") from None
            steps.append(ai_step(params))
        receipt = run(args.table, steps, status_col=args.status_col, where=args.where,
                      workers=args.workers, limit=args.limit, commit=args.commit,
                      db=args.db)
    except (RunnerError, dbmod.DbError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False),
              file=sys.stderr)
        return 1
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
