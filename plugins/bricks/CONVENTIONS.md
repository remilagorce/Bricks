# Bricks conventions

The shared contract between all Bricks skills. Skills never talk to each
other directly — they communicate through the workspace database described
here. Every skill MUST follow the workspace-resolution procedure below
before doing anything else.

## 1. Data layout

All data lives in `bricks/` at the root of the user's current working
directory — never inside the plugin, never in `~/.claude`.

```
bricks/
  config.json                      # single source of truth: current workspace
  workspaces/
    <name>/
      workspace.json               # metadata: name, goal, createdAt, status
      bricks.db                    # SQLite database — THE data bus (WAL mode)
      context/                     # the client brain — human-editable
        offer.md                   #   what we sell, proof points, tone
        icp.md                     #   ideal customer profile + kill rules
        personas/                  #   one file per buyer persona
      staging/                     # raw provisional payloads (jsonl) before commit
      memory/
        state.json                 # structured state: steps done, cursors, quotas
        NOTES.md                   # free-form working memory
```

## 2. Workspace resolution (mandatory preamble)

Before any read or write, every skill runs:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workspace.py" status
```

Then acts on the result:

1. **`initialized: false`** → automatically run
   `python3 "${CLAUDE_PLUGIN_ROOT}/tools/workspace.py" init`. Do not ask
   permission for this — it only creates `bricks/config.json`.
2. **`currentWorkspace: null`** → a workspace is needed. If the user's
   request implies a name (a client, a campaign, an ICP), create it with
   `new <name> --goal "..."`; otherwise ask the user for a name.
3. **Otherwise** → work exclusively inside the `current.path` returned by
   `status`. Read `memory/state.json` and `memory/NOTES.md` to pick up
   context before acting.

Never write outside the current workspace. Never guess a workspace: if the
user seems to target another one, run `switch` first. Never edit
`config.json` by hand — only through `tools/workspace.py`.

**Workspace banner.** `new` and `switch` return a `banner` (a `####` box
with the workspace name) and a `welcome` line. Whenever the workspace
changes, display the banner to the user VERBATIM in a fenced code block,
immediately followed by the welcome line, before anything else. The
SessionStart hook shows the same banner at session open — this is how the
user always knows which world they are in.

## 3. Context gate & drift guardrail (mandatory check)

`context/` is the client brain. Before any sourcing (find), enrichment or
writing task, read `context/offer.md` and `context/icp.md` of the CURRENT
workspace (and the relevant `personas/` file for writing tasks). If they
are still TODO placeholders, offer to fill them first — three quick
questions: what do you sell (one sentence)? who is the ideal customer? any
hard disqualifiers (size, country…)?

**Drift guardrail.** If the user's request contradicts the current
workspace's context — a different product than `offer.md`, a different
target than `icp.md`, a company that a kill rule excludes — STOP before
writing anything and ask which they want:

1. `switch` to the workspace that matches the request,
2. create a `new` workspace for it, or
3. update this workspace's `context/` (the request supersedes the files).

Never mix two clients or two offers inside one workspace.

## 4. FullEnrich connection gate (mandatory check)

Bricks ships with the `fullenrich` MCP server (waterfall enrichment over
20+ providers). At the start of every skill run — right after resolving
the workspace — check whether `mcp__fullenrich__*` tools are present in
your tool list:

- **Present** → the user is signed in; proceed silently.
- **Absent** → the user is NOT signed in. Tell them immediately how to
  connect: run `/mcp`, pick `fullenrich`, sign in with their FullEnrich
  account in the browser. Then:
  - If the task consumes enrichment data (enrich, contact/email/phone
    sourcing) → **STOP until connected**. Never fabricate values and never
    scrape around the gate.
  - Otherwise (workspace ops, transform, interface) → warn once and
    continue; the task does not depend on FullEnrich.

## 5. Database rules — delegate to the db-writer agent

Each workspace has one SQLite database, `bricks.db` (WAL mode: parallel
writers can work safely). **Every** read and write goes through
`tools/db.py` — but skills do not call it themselves. Skills delegate the
operation, in natural language, to the **`db-writer` agent**
(`agents/db-writer.md`): "insert these company rows, dedup on domain",
"claim 25 pending rows for employees_status", "write employees=120 for id
3". `db-writer` is the single place that knows `db.py`'s exact CLI —
keeping that knowledge in one file instead of duplicated across every
`SKILL.md` is the whole point: change the tool and the agent together,
instead of hunting down every skill that embeds an example command.

Never raw `sqlite3`, never hand-rolled SQL in the conversation, never any
tool other than `db-writer` touching `bricks.db`. `db.py` resolves the
current workspace automatically (it reads `bricks/config.json`). Every
command prints JSON; a non-zero exit code means the database was NOT
modified — `db-writer` reports that back plainly, never retries blindly.

The reference below is `db-writer`'s own contract with the tool — read it
if you are implementing or debugging `db-writer` itself, or `db.py`. A
skill author does not need to memorize this; describe the intent and let
`db-writer` translate it.

Tables and columns are dynamic, Clay-style — `add` creates the table on
first use, `add`/`modify` create missing columns on the fly:

```bash
# Insert rows (creates table/columns as needed); --key dedups on a column
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" add companies \
  --rows '[{"name": "Acme", "domain": "acme.com", "source": "fullenrich"}]' --key domain

# Read rows (default limit 50 — receipts, not dumps)
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" select companies \
  --where "employees_status='pending'" --cols _id,domain --limit 50

# Update cells by _id (all-or-nothing; unknown columns created automatically)
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" modify companies \
  --updates '[{"_id": 3, "employees": 120, "employees_status": "done"}]'

# Bulk claim / bulk set (requires --where)
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" modify companies \
  --set employees_status=running --where "_id IN (3,4,5)"

# Delete by _id (race-free) or by condition
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" remove companies --ids '[3, 7]'
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" remove companies --where "status='disqualified'"

# Inspect / import
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" tables
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" import-csv companies <exported-list.csv> --key domain
```

For large payloads, pass `--rows -` / `--updates -` / `--ids -` and pipe
the JSON via stdin.

- **`_id` is the reserved technical column** (INTEGER PRIMARY KEY):
  generated by the database, never set, never modified, never displayed —
  the front hides every `_`-prefixed column. Address rows by `_id`; ids
  never shift, row numbers do not exist here.
- Besides `_id`, a business key column (`domain`, `email`…) is recommended;
  pass it as `--key` on `add` to dedup on insert.
- **Standard columns** — `companies`: `name, domain, source, status` plus
  enrichment columns. `contacts`: `company_id` (the company's `_id`),
  `full_name, role, email, linkedin_url, source, status`.

### Status columns — the shared vocabulary

An enrichment column `X` is paired with `X_status`. Exact values, same
meaning everywhere:

| Status | Meaning |
|---|---|
| `pending` | Work not started (set it when creating the column) |
| `running` | A run claimed these rows and is working on them |
| `done` | Value written, usable downstream |
| `not_found` | Work completed, nothing found — a result, not an error |
| `failed` | Something broke — eligible for retry |

Row-level `status`: `new` (live) or `disqualified` (killed by a kill rule —
never spend anything on it again). Message-like rows (sequences, emails)
carry `draft` → `approved` → `sent`; skills only ever write `draft` —
approval is a human act, and nothing leaves the machine without it.

### The three iron rules

1. Mark `running` (bulk `--set` on the claimed `_id`s) BEFORE working;
   write each result and its final status IMMEDIATELY after each row —
   never batch-write at the end. An interrupted run must lose at most one
   row of work.
2. Select work with `WHERE <col>_status='pending' AND status!='disqualified'`
   (re-runs add `OR <col>_status='failed'`). Re-running a skill must never
   reprocess `done` rows — idempotence by statuses, no separate cursor
   needed for row-by-row work.
3. Data flows through the database, never through the conversation. Skills
   ask `db-writer` to write results as they arrive and relay its receipts:
   counts and at most 3 sample rows. Never dump tables into the chat.

## 6. Staging: raw payloads before commit

`staging/` is the scratch area for RAW source payloads when the work is
**voluminous**, **long** (interruption risk) or **asynchronous** (FullEnrich
bulk jobs). Append raw results to
`staging/<skill>-<YYYY-MM-DD>/raw-results.jsonl`, track rejects with a
reason in `rejected.jsonl`, store async job/batch ids in
`memory/state.json` (an interrupted run must fetch results later instead of
paying twice). Then validate, map to columns, and commit to the database
via `db.py add --key …`. For a handful of rows in a single run, skip
staging and write the database directly.

## 7. Memory discipline

- `memory/state.json` — structured, machine-read: pagination cursors on
  external sources, quotas used, async job ids. Row-level progress lives in
  the status columns, not here. Update it at the end of every run.
- `memory/NOTES.md` — free-form, human-read: decisions, context, open
  questions. Append at the bottom, newest last. Never rewrite history.

## 8. Paid actions — the money gate

Applies to ANY action that consumes credits or money: FullEnrich enrichment
and exports, Bright Data requests at volume, any metered API. The protocol,
in order, no exceptions:

1. **Preview free first** when the provider offers it (FullEnrich search
   returns 10 results + total count at no cost; a single Bright Data page
   scout costs 1 credit).
2. **Announce before spending**: the exact volume, the unit cost, and the
   estimated total ("N contacts × 1 credit each").
3. **Explicit confirmation** from the user. Silence is not consent.
4. **Hard caps without an explicit override**: 50 paid enrichments, 100
   sourced candidates, 10 scraped pages per run.
5. **Never spend on the dead**: rows with `status='disqualified'` (or whose
   parent company is disqualified) never consume a credit again.
6. **Never pay twice**: statuses make re-runs skip `done` rows; async
   job/batch ids live in `memory/state.json` (§6) so an interrupted run
   fetches results instead of re-submitting.

## 9. Brick contracts — BRICK.md

Every skill directory carries a `BRICK.md`: the machine-checkable summary of
its contract. IN (columns + status preconditions it reads), OUT (columns +
statuses it writes), method, cost class (`free` | `cheap` | `paid`), error
statuses. One page maximum. It is the file another teammate (or the docs
generator) reads to know what the brick does without opening the SKILL —
and the file a reviewer diffs to catch a contract change.
