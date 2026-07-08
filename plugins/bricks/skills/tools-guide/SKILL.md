---
name: tools-guide
description: Reference for every Bricks Python tool — workspace, db, runner, agent, providers — in BOTH call modes (CLI and Python function). Use when the user asks how to call a tool, what a CLI command does, which function to use for a task, or "comment utiliser db.py / runner.py / agent.py".
user-invocable: true
---

# Tools guide — how to call each Bricks script

The shared runtime contract is `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` — this
guide is the tool-by-tool reference behind it.

Core scripts live under `${CLAUDE_PLUGIN_ROOT}/tools/core/`, provider adapters
under `${CLAUDE_PLUGIN_ROOT}/tools/providers/`. Every script prints **JSON on
stdout** (errors on stderr, exit 1) AND is importable as plain Python functions
— same code paths both ways. Skills orchestrate; tools execute.

CLI prefix:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/<script>.py" ...
```

Function mode (from a step file or any script):

```python
import sys; sys.path.insert(0, "<plugin>/tools/core")
import db, workspace, runner, agent
```

Database path: omit `--db` to use the **current workspace** (`bricks/config.json`).
Override with `--db /path/to/bricks.db` — accepted BEFORE or AFTER the
subcommand.

---

## workspace.py — project lifecycle

| Command | Purpose |
|---|---|
| `status` | Current workspace, db path, tables, context files |
| `list` | All workspaces + which is current |
| `new <name>` | Create workspace (copies `context/` templates, inits db, switches to it) |
| `switch <name>` | Point `config.json` at another workspace |

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/workspace.py" status
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/workspace.py" new acme-outbound
```

**When to use:** always run `status` before any GTM work. Never edit
`config.json` by hand.

---

## db.py — the only door to the database

Dynamic tables/columns (Clay-style). `_id` is auto-generated — never pass it in
`add`. All mutations are all-or-nothing; parallel writers are safe (WAL +
immediate transactions).

### Read

| Command | Purpose |
|---|---|
| `tables` | List tables with row counts and column names |
| `schema <table>` | Column list + total rows |
| `select <table>` | Query rows (`--where`, `--cols`, `--limit` [-1 = all], `--offset`, `--order`) |
| `count <table>` | Count without reading rows (`--where`) |

### Write

| Command | Purpose | When |
|---|---|---|
| `add` | Insert rows from a JSON list (`--rows '[…]'` or `-` = stdin; `--key` dedups) | Small pass-through data (≤ ~50 rows) |
| `import-csv <table> <file>` | Insert rows from a CSV (`--key` dedups) | **Sourcing** — any external mass (§6) |
| `modify --updates '[{"_id":3,…}]'` | Update cells by `_id` | Patch specific rows |
| `modify --set col=v --where SQL` | Bulk update (requires `--where`; `--where 1=1` targets all) | Init a status column, reset statuses |
| `claim <table> <status_col>` | **Atomically** select up to `--limit` pending rows AND mark them `running` (`--retry-failed` widens to failed; disqualified rows never claimed) | Take work safely — two parallel runs can never claim the same rows |
| `remove --ids '[3,7]'` / `remove --where SQL` | Delete rows | Drop rows |
| `drop-column <table> <col>` | Drop one column, rows preserved | Undo a bad column |
| `drop-table <table> --confirm` | Delete a whole table — irreversible | Start over |

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" add companies \
  --rows '[{"name":"Acme","domain":"acme.com"}]' --key domain
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" import-csv companies ./bricks/tmp/companies.csv --key domain
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" modify companies --set hq_status=pending --where "domain IS NOT NULL"
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" claim companies hq_status --limit 25 --cols _id,domain
```

Function mode: `db.resolve(db=None)`, `db.connect(path)`, `db.columns(conn, t)`,
plus one function per command — `db.select(path, table, where=None, cols=None,
limit=None, offset=0, order=None)`, `db.add(path, table, rows, key=None)`,
`db.modify(path, table, updates=None, sets=None, where=None)`,
`db.claim(path, table, status_col, limit=25, cols=None, where=None,
retry_failed=False)`, `db.remove(path, table, ids=None, where=None)`,
`db.count`, `db.import_csv`, `db.drop_table`, `db.drop_column`. All return the
same dict as the CLI's JSON; all raise `db.DbError` on invalid input.

**Never:** raw SQL, `sqlite3` CLI, or mass data inlined in the conversation.

---

## runner.py — THE loop (batch work, preview → GO → commit)

One pipeline of steps per row, rows in parallel, claims by tranches, writes in
waves, one reconciled receipt. **Always preview first** (§5).

### `run`

| Flag | Purpose |
|---|---|
| `--table` | Target table (required) |
| `--status-col` | The `X_status` checkpoint column, claimed on `pending` (required) |
| `--run-id` | Tag written on every row — `rollback` erases by it (required) |
| `--preview N` \| `--commit` | Exactly one: N pilot rows (written tagged + streamed), or the whole table tranche by tranche |
| `--step 'file.py:fn'` | Custom step, repeatable, run in order |
| `--step 'file.py:fn {"k":"v"}'` | Same, with JSON args — the first `{` starts the args object |
| `--ai '{…}'` | Built-in AI step, always last (see below) |
| `--where SQL` | Extra condition ANDed to the claim |
| `--retry-failed` | Also claim `failed` rows (explicit retry pass) |
| `--limit` | Tranche size (default 500) |
| `--workers` | Parallel rows (default 12, cap 50) |
| `--out-table` | Table receiving child rows inserted by provider steps (recorded in the manifest for rollback) |
| `--no-retry-timeout` | Fail fast on timeout — first rung of an escalation ladder |
| `--db`, `--manifest` | Overrides (manifest default: next to bricks.db) |

`--ai` params: `{"prompt":"…{{col}}…","schema":{"type":"object","properties":
{"col_out":{"type":"string","description":"…"}}},"web":true,"model":"haiku",
"evidence":true,"input_cols":"all|none|a,b","max_pages":5,"timeout":120}`.
`{{col}}` reads the row **including fields produced by earlier steps**;
`schema.properties` = the columns to write; the answer envelope
(`status done|not_found` + fields + `evidence`) is guaranteed by the platform.

**Step contract** (a plain function in any Python file):

```python
def step(row: dict, ctx: dict, args: dict) -> dict:   # args optional (2-param OK)
    # ctx = {"db", "table", "commit", "preview", "run_id", "out_table"}
    # return: fields to write on the row (merged into row for the next step)
    # exception -> that row is 'failed', the run continues
    # child rows inserted elsewhere MUST carry source_run=ctx["run_id"]
```

**Preview streaming:** `--preview N` emits NDJSON on stderr (`preview_start`,
then one `preview_row` per finished row) — relay each line to the user while
the command runs; stdout is the final receipt only.

```bash
# PREVIEW — 10 pilot rows, written tagged, streamed live
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/runner.py" run --table companies \
  --status-col hq_status --run-id hq-2026-07-09 \
  --ai '{"prompt":"Ville du siège de {{name}} ({{domain}}) ?","schema":{"type":"object","properties":{"hq_city":{"type":"string"}}},"web":true}' \
  --preview 10

# COMMIT — same command, --preview 10 → --commit, after the user's GO
```

### `rollback` & `release`

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/runner.py" rollback --manifest <run>.manifest.json
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/runner.py" release --table companies --status-col hq_status
```

`rollback` nulls the run's fields, resets statuses to `pending`, removes child
rows (`source_run`). `release` frees rows a crash left `running`.

Function mode: `runner.rollback(manifest_path)`, `runner.release(db, table,
status_col)`; the run loop itself is CLI-first (it owns argv defaults).

**When to use:** enrichment mode B — values computed or fetched per row. For
pass-through data use `db.py add`/`import-csv` instead.

---

## agent.py — ONE prompt, ONE answer (the unit brain)

The single AI-calling function of the project: every model call outside the
session goes through it — fired directly (one row) or per row by `runner.py`.
The session always compiles the prompt; the agent executes.

| Flag / param | Purpose |
|---|---|
| `--prompt` / `--prompt-file` | The mission (required) |
| `--schema '{…}'` | JSON Schema — the answer is GUARANTEED to validate |
| `--web` | Bright Data browsing (`BRIGHTDATA_API_TOKEN`), capped by `--max-pages` |
| `--model` | e.g. `haiku` (default: session default) |
| `--timeout` | Seconds (default 120) |

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/agent.py" \
  --prompt "Ville du siège de acme.com ?" --web --model haiku \
  --schema '{"type":"object","properties":{"hq_city":{"type":"string"}}}'
```

Function mode: `agent.agent(prompt, web=False, schema=None, model=None,
max_pages=5, timeout=120)` → `str`, or `dict` when `schema` is given; raises
`agent.AgentError`.

**Transports & billing:** default = Claude Agent SDK driving the local CLI
(subscription; isolated MCP config — the worker gets exactly the tools it asks
for). `BRICKS_AGENT_TRANSPORT=api` routes the SAME call through the Anthropic
Messages API (API credits; `ANTHROPIC_API_KEY` in `~/.bricks/env`) — required
where the SDK cannot run (Python < 3.10, no AVX). An `ANTHROPIC_API_KEY`
present in the env takes precedence over the subscription login on BOTH paths.

**When to use:** isolated one-off research (≲5 rows — see `/bricks:brickgent`).
For table-wide enrichment, go through `runner.py`, never repeated `agent.py`
calls.

---

## tools/providers/ — deterministic provider adapters

Provider-facing plumbing (HTTP, RSS, scraping) — zero model. Each exposes a
CLI AND a `step(row, ctx, args)` function that plugs into `runner.py --step`.

| Script | Purpose | Runner step |
|---|---|---|
| `firmo.py` | French official firmographics (recherche-entreprises.api.gouv.fr, free) | `firmo.py:step` — reads `name`, writes siren/employees/industry/executives… |
| `fullenrich.py` | FullEnrich people search, wave cascade per company (`FULLENRICH_API_KEY`) | `fullenrich.py:step {"params":{…},"out_table":"contacts"}` — inserts verified contacts as child rows tagged `source_run` |
| `jobs.py` | Hiring-signal hunt/check (France Travail, HelloWork, career pages — free) | CLI `hunt --matrix` / `check --companies` → JSONL in `--out` |
| `news.py` | Company news via Google News RSS (free) | CLI `--companies --out [--days] [--terms]` → JSONL |

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/runner.py" run --table companies \
  --status-col firmo_status --run-id firmo-2026-07-09 \
  --step "${CLAUDE_PLUGIN_ROOT}/tools/providers/firmo.py:step" --preview 10
```

---

## Quick decision tree

```
Need a workspace?            → workspace.py status | new | switch
Read what's in the db?       → db.py tables | schema | select | count
Insert user-owned data?      → db.py add --rows '[{...}]'  (small)
Insert sourced mass?         → save CSV → db.py import-csv <table> <file> --key <col>
Patch existing rows?         → db.py modify (--updates | --set+--where)
Enrich many rows (AI)?       → runner.py run --ai … --preview 10 → GO → --commit
Enrich many rows (provider)? → runner.py run --step providers/<x>.py:step …
Chain both on one pass?      → runner.py run --step … --step … --ai …
Undo a bad run?              → runner.py rollback --manifest <run>.manifest.json
One-off AI question (≲5)?    → agent.py --prompt … (or /bricks:brickgent)
GTM sourcing / enrichment?   → /bricks:find | /bricks:enrich
No ICP yet?                  → /bricks:gtm-onboard
```
