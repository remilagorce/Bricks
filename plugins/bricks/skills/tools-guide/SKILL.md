---
name: tools-guide
description: Reference for every Bricks Python tool — workspace, db, runner, agent. Use when the user asks how to call a tool, what a CLI command does, which function to use for a task, or "comment utiliser db.py / runner.py".
user-invocable: true
---

# Tools guide — how to call each Bricks script

The shared runtime contract is `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` — this
guide is the tool-by-tool reference behind it.

All scripts live under `${CLAUDE_PLUGIN_ROOT}/tools/core/`. Every script prints
**JSON on stdout** (errors on stderr, exit 1). Skills orchestrate; tools execute.

Prefix every command with:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/<script>.py" ...
```

Database path: omit `--db` to use the **current workspace** (`bricks/config.json`).
Override with `--db /path/to/bricks.db` or `--root bricks`.

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
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/workspace.py" switch acme-outbound
```

**When to use:** always run `status` before any GTM work. Create or switch
workspaces when the project changes — never edit `config.json` by hand.

---

## db.py — the only door to the database

Dynamic tables/columns (Clay-style). `_id` is auto-generated — never pass it in
`add`. All mutations are all-or-nothing.

### Read

| Command | Purpose |
|---|---|
| `tables` | List tables with row counts and column names |
| `schema <table>` | Column list + total rows |
| `select <table>` | Query rows (`--where`, `--cols`, `--limit`, `--offset`) |

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" tables
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" schema companies
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" select companies --where "domain IS NOT NULL" --limit 10
```

### Write — pick ONE path per task (see CLAUDE.md Rules 6–7)

| Command | Purpose | When |
|---|---|---|
| **`add`** | **Insert rows** from a JSON list of objects | Small pass-through data the user already has (≤ ~50 rows, enrichment mode A). Not for sourced lead lists. |
| `import-csv` | Insert rows from a CSV file (positional arg) | **Sourcing** — MCP export, scrape, any external mass (Rule 6) |
| `modify` | Update existing rows by `_id` | Patch columns on rows already in the table |
| `remove` | Delete rows by `_id` | Drop rows |

**`add` — insert a list of objects (CLI):**

```bash
# inline JSON
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" add companies \
  --rows '[{"name":"Acme","domain":"acme.com","source":"manual"}]' \
  --key domain

# from stdin (pipe or heredoc)
echo '[{"name":"Beta","domain":"beta.io"}]' | \
  python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" add companies --rows - --key domain
```

Receipt fields: `added`, `skippedDuplicates`, `newColumns`, `created` (true if
table was created), `rows` (total count after insert).

**`import-csv` — insert from file:**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" import-csv companies ./bricks/tmp/companies.csv --key domain
```

**`modify` — update by `_id`:**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" modify companies \
  --updates '[{"_id":3,"hq_city":"Nantes","hq_status":"done"}]'
```

**Never:** raw SQL, `sqlite3` CLI, or mass data inlined in the conversation.

---

## runner.py — batch enrichment loop

One pipeline, all eligible rows, in parallel. Zero intelligence in the loop —
each step is a plain function. **Always preview first** (Rule 2).

| Flag | Purpose |
|---|---|
| `--table` | Target table (required) |
| `--ai '{...}'` | Built-in AI step: `prompt` with `{{column}}`, `schema.properties` = columns to write, optional `web`, `model` |
| `--step file.py:fn` | Custom Python step (repeatable, in order) |
| `--status-col` | Checkpoint column (`hq_status`) — required with `--commit` |
| `--where` | Extra SQL filter |
| `--commit` | Write results (only after preview + user GO) |
| `--limit` | Preview caps at 10; commit processes all pending rows |

```bash
# PREVIEW — writes nothing
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/runner.py" --table companies \
  --ai '{"prompt":"HQ city for {{name}} ({{domain}})","schema":{"type":"object","properties":{"hq_city":{"type":"string"}}},"web":true,"model":"haiku"}' \
  --status-col hq_status

# COMMIT — same command + --commit after user GO
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/runner.py" --table companies \
  --ai '{"prompt":"HQ city for {{name}} ({{domain}})","schema":{"type":"object","properties":{"hq_city":{"type":"string"}}},"web":true,"model":"haiku"}' \
  --status-col hq_status --commit
```

**When to use:** enrichment mode B — values must be computed or fetched per row.
For pass-through data the user already has, use `db.py add` or `import-csv`
instead.

---

## agent.py — one prompt, one answer

Single AI call outside the session loop. Used directly for 1–few rows, or
internally by `runner.py` per row.

| Flag | Purpose |
|---|---|
| `--prompt` / `--prompt-file` | The question (required) |
| `--schema '{...}'` | Guaranteed JSON output matching schema |
| `--web` | Enable Bright Data browsing (`BRIGHTDATA_API_TOKEN`) |
| `--model` | e.g. `haiku` (default: subscription default) |

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/agent.py" \
  --prompt "What is the HQ city of acme.com?" --web --model haiku \
  --schema '{"type":"object","properties":{"hq_city":{"type":"string"}}}'
```

**When to use:** isolated one-off research (handful of rows). For table-wide
enrichment, use `/bricks:enrich` → `runner.py`, not repeated `agent.py` calls.

---

## Quick decision tree

```
Need a workspace?          → workspace.py status | new | switch
Read what's in the db?   → db.py tables | schema | select
Insert user-owned data?  → db.py add --rows '[{...}]'  (small)
Insert sourced mass?     → save CSV → db.py import-csv <table> <file>
Patch existing rows?     → db.py modify --updates '[{"_id":N,...}]'
Enrich many rows (AI)?   → runner.py --ai ... (preview) → --commit
One-off AI question?     → agent.py --prompt ...
GTM sourcing?            → /bricks:find
GTM enrichment?          → /bricks:enrich
No ICP yet?              → /bricks:gtm-onboard
```
