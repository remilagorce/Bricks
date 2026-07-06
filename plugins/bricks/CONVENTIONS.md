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

**Never name the context files to the user.** `offer.md`, `icp.md`,
`personas/…` are internal plumbing. Talk about their *content* freely ("ton
ICP vise les cliniques privées", "d'après ton offre…") but never surface the
file names or paths ("j'ai écrit dans `context/icp.md`", "regarde
`offer.md`") — the user reasons about their GTM, not about our file tree.
The only exception is when the user explicitly asks where something is
stored.

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

## 5. Database rules — call db.py directly

Each workspace has one SQLite database, `bricks.db` (WAL mode: parallel
writers can work safely). **Every** read and write goes through
`tools/db.py` — called **directly**, following the contract below. No
subagent sits between a skill and the database: `db.py` is deterministic,
injection-safe and already prints JSON with counts, so there is nothing to
delegate to a model. Run it with the `Bash` tool like any other Bricks
plumbing (`workspace.py`, `firmo.py`, `jobs.py`…): describe the write to
the user in one line, run the command, relay its JSON receipt.

This section IS the single source of truth for `db.py`'s CLI. Keeping the
contract in one file (here, referenced by every skill) instead of embedding
example commands in each `SKILL.md` is the whole point: change the tool and
this section together, in the same commit. A skill author does not memorize
flags — a skill says "write results to the DB per CONVENTIONS §5" and the
main thread applies the matching command from the reference below.

Never raw `sqlite3`, never hand-rolled SQL in the conversation, never any
tool other than `db.py` touching `bricks.db`. `db.py` resolves the current
workspace automatically (it reads `bricks/config.json`). Every command
prints JSON; a non-zero exit code means the database was NOT modified —
read the JSON error on stderr and report it plainly, never retry blindly.

**Always pass the absolute database path** with `--db <path>` (the current
workspace's `bricks.db`, from `workspace.py status`). When a skill delegates
a batch to a subagent (volume mode: parallel find/enrich workers), those
subagents write their RAW findings to `staging/` only — the main thread
resolves the path once and does every `db.py` write itself, so a write can
never land in the wrong database because a subagent didn't inherit the cwd.

Tables and columns are dynamic, Clay-style — `add` creates the table on
first use, `add`/`modify` create missing columns on the fly:

Every command below takes `--db <absolute path to bricks.db>` (omitted from
the examples for readability — never omit it in a real call).

```bash
# Insert rows (creates table/columns as needed); --key dedups on a column
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" add companies \
  --rows '[{"name": "Acme", "domain": "acme.com", "source": "fullenrich"}]' --key domain

# Read rows (default limit 50 — receipts, not dumps)
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" select companies \
  --where "employees_status='pending'" --cols _id,domain --limit 50

# Count without reading rows
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" count companies --where "status!='disqualified'"

# Claim work: atomically select up to N pending rows AND mark them running
# (one command instead of select + modify; disqualified rows never claimed;
#  --retry-failed widens to 'failed' rows on an explicit retry)
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" claim companies employees_status \
  --limit 25 --cols _id,name,domain

# Update cells by _id (all-or-nothing; unknown columns created automatically)
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" modify companies \
  --updates '[{"_id": 3, "employees": 120, "employees_status": "done"}]'

# Bulk claim / bulk set (requires --where; use --where 1=1 to really target all rows)
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" modify companies \
  --set employees_status=running --where "_id IN (3,4,5)"

# Delete by _id (race-free) or by condition
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" remove companies --ids '[3, 7]'
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" remove companies --where "status='disqualified'"

# Inspect
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" tables
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" schema companies

# Import a CSV / drop a column / drop a whole table (drop-table is irreversible)
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" import-csv companies <exported-list.csv> --key domain
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" drop-column companies stale_col
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" drop-table staging --confirm
```

For large payloads, pass `--rows -` / `--updates -` / `--ids -` and pipe
the JSON via stdin instead of an inline argument.

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

1. Mark `running` BEFORE working — `db.py claim` does select + mark in
   ONE atomic command (preferred: two parallel runs can never claim the
   same rows); write results and their final status as soon as they
   land — one `db.py` write per row for serial work, ONE write per
   completed wave for parallel work (§9) — never accumulate a whole run
   and write at the end. An interrupted run must lose at most one row or
   one wave of work.
2. Work selection is what `claim` encodes: `<col>_status='pending'` AND
   not disqualified (an explicit retry adds `--retry-failed`).
   Re-running a skill must never reprocess `done` rows — idempotence by
   statuses, no separate cursor needed for row-by-row work.
3. Data flows through the database, never through the conversation. Skills
   run the `db.py` write as results arrive and relay its JSON receipt:
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

## 8. Paid actions — the big-spend gate

Applies to ANY action that consumes credits or money: FullEnrich
enrichment and exports, Bright Data requests, any metered API. One
principle: **full autonomy, except when a lot of credits are about to
go out at once** — that, and only that, gets ONE question.

1. **Free first, always**: free lanes and deterministic scripts
   (`tools/*.py`) before paid ones; provider previews when they exist
   (FullEnrich searches are free; one Bright Data control query = 1
   credit).
2. **Autonomy by default**: paid work below the big-spend threshold
   runs with NO confirmation — the plan is announced in a line as it
   starts, and the receipt shows the actual spend plus the session's
   cumulative total. Transparency after, not permission before. No
   per-run or per-week accounting, no envelope bookkeeping.
3. **The big-spend threshold**: default **50 credits for one
   batch/action**. The user changes it by just saying so ("seuil à
   100") — persisted as `spend_threshold` in `memory/state.json`.
   Above it → ONE grouped authorization phrased as the batch it
   covers, fallbacks included ("les ~100 prochains contacts ≈ 100
   crédits, FullEnrich d'abord, scrape en fallback — GO ?"). Once
   given, it covers the whole batch; only exceeding the AUTHORIZED
   amount comes back to the user.
4. **Never spend on the dead**: rows with `status='disqualified'` (or
   whose parent company is disqualified) never consume a credit again.
5. **Never pay twice**: statuses make re-runs skip `done` rows; async
   job/batch ids live in `memory/state.json` (§6) so an interrupted run
   fetches results instead of re-submitting.
6. **Business inputs are not money gates**: strategy, matrices, voice,
   signature are asked ONCE per workspace, grouped in a single block,
   persisted — never re-asked while `context/` is unchanged. Receipts
   end with statements, never questions.

## 9. Parallelism — waves, not rows

The slow shape is the sequential waterfall: finish row 1 (rung A → B →
C), then row 2, then row 3… Every network call costs seconds; serializing
N rows makes the run linear in N. The fast shape is the WAVE: run ONE
rung across the whole batch at once, then run the next rung only on the
rows the previous wave left unresolved. N sequential waterfalls become
~3 parallel waves — same rungs, same verification rule, same cost order.

1. **One rung, whole batch, one message.** Independent tool calls (MCP
   searches, scrapes, fetches) belonging to the same wave are fired IN
   PARALLEL in a single message — never await one row's result before
   firing the next row's call. Waiting is only legal BETWEEN waves
   (wave B needs wave A's misses) or when one call's input depends on
   another call's output.
2. **Prefer the batch variant of a tool** when it exists: one call
   carrying N inputs beats N parallel calls. FullEnrich `enrich_bulk`
   (async job — store the job id in `memory/state.json`, §8.5) over
   per-contact enrichment; Bright Data `search_engine_batch` over serial
   `search_engine` queries, `scrape_batch` over serial
   `scrape_as_markdown`. Same spend, one round-trip.
3. **Cost order lives BETWEEN waves, not within a row**: wave A (free)
   on all rows in scope → wave B (paid) only on A's misses → wave C on
   B's misses. §8 is untouched — cheap first still holds, per wave, and
   the upfront budget announcement covers the worst case exactly as
   before.
4. **Write per wave** (iron rule 1): claim `running` on the batch, then
   ONE `db.py` write per completed wave — not one per row (dispatch
   overhead), not one at the end of the run (interruption loses
   everything).
5. **Subagents are for volume, not for structure.** Each subagent is a
   cold start that re-derives context — below ~40 rows, parallel waves
   in the main thread beat spawning workers. Above ~40 rows: subagent
   batches (5-8 rows each, up to 10 in parallel) that run the waves and
   append findings to `staging/` (§6); the main thread verifies and
   commits. Subagents never write the database and never spend beyond
   the announced budget.
6. **Progress lives in statuses, never in mid-run displays.** The front
   reads the database live — a column updates in the UI when its wave
   commits. Never pause a run to show intermediate tables in the chat,
   never wait for the user mid-wave: one announcement at start, receipts
   at the end (§8).
