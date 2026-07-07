# Bricks — project rules

Bricks is an open-source, Claude-native alternative to Clay: GTM workflows
(find, enrich...) backed by a per-workspace SQLite database, driven from
Claude Code.

## The architecture, in one sentence

`tools/` is the application's control logic — plain Python, every script
callable BOTH as a CLI and as importable functions; `skills/` are the
instruction manuals that tell the AI how to act and how to drive the
application through those tools.

**Two audiences, two contracts.** This `CLAUDE.md` is for whoever *builds and
maintains* the repo (you, right now). `plugins/bricks/CONVENTIONS.md` is the
*runtime* contract every skill reads before acting (workspace resolution,
context gate, the only door, the iron gate). Keep CONVENTIONS.md short — when a
rule outgrows a few lines it belongs in a tool or a skill, not there. The Bricks
root is initialized once by the SessionStart hook (`workspace.py init`), so no
skill ever checks-and-inits.

## Rule 1 — logic lives in tools, never in skills

Always reuse the existing functions first. When a new need appears (e.g. a
new kind of database write), write the function in the appropriate file
under `plugins/bricks/tools/` and have the skill call the script in CLI
mode. Never bury logic in a SKILL.md, never hand-write SQL in the
conversation. A script that is truly specific to one skill may live in that
skill's directory; anything reusable goes to `tools/`.

The core files and their single responsibilities:

- `tools/core/workspace.py` — workspace lifecycle. One directory per
  workspace (`bricks/workspaces/<slug>/` with `bricks.db` + `context/`),
  one pointer file (`bricks/config.json`).
- `tools/core/db.py` — the ONLY door to a workspace database. Dynamic
  tables/columns (Clay-style), `_id` reserved, JSON receipts. Write waves
  in ONE call (`modify --updates '[...]'`), never one CLI call per row —
  per-row dispatches were the single biggest slowness of the previous
  version.
- `tools/core/agent.py` — the single AI-calling function: one prompt, one
  answer, optional Bright Data web research, optional guaranteed JSON
  schema output. Runs on the Claude subscription by default.
- `tools/core/runner.py` — THE loop: a pipeline of steps per row, rows in
  parallel. Zero intelligence; what happens to a row is a step function.

## Rule 2 — preview before any mass write (the iron gate)

Every bulk action runs `runner.py` WITHOUT `--commit` first: it computes
the first 10 rows, shows every result, and writes NOTHING. The user gives
ONE explicit GO; only then does `--commit` process and write the mass.
Statuses (`pending/running/done/failed` in a `X_status` column) are the
checkpoint — re-running resumes the pending rows.

## Rule 3 — bump the version on every plugin change

Installed plugins are cached BY VERSION: if `plugins/bricks/` changes but
the version stays the same, `claude plugin update` answers "already at
latest" and sessions silently run the stale cache. Any change under
`plugins/bricks/` ships with a version bump in BOTH
`plugins/bricks/.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json`.

## Rule 4 — stay small

The core files have size budgets: db ~200 lines, runner ~150, agent ~100,
workspace ~150. Growing past them is a smell: the feature probably belongs
in a new step function, a new tool file, or the ROADMAP — not in the core.
Features removed from the previous version (atomic claim, rollback,
manifests, the web UI) come back one by one WHEN the need returns, not
preemptively.

## Rule 5 — skills: create with the official plugin, reference by slash command

When creating or rewriting a skill under `plugins/bricks/skills/`, use the
official Claude skill tooling — do not improvise structure from scratch:

1. Install once: `/plugin install skill-creator@claude-plugins-official` (and
   `/plugin install plugin-dev@claude-plugins-official` for plugin-specific
   layout and conventions).
2. Before writing a new skill, invoke **`/plugin-dev:skill-development`**.
   When iterating or evaluating an existing skill, use **`/skill-creator:skill-creator`**.

Whenever a skill, doc, or handoff mentions another Bricks skill, write it as
a slash command — never as a file path, never as bold text alone:

- `/bricks:find`
- `/bricks:enrich`
- `/bricks:gtm-onboard`
- `/bricks:tools-guide`

Pattern: `/bricks:<skill-directory-name>` (the folder name under `skills/`,
not a path to `SKILL.md`). Example handoff: *"If no ICP → invoke
`/bricks:gtm-onboard` before continuing."*

## Rule 6 — one logical pipeline; sourcing goes through a CSV file

Every capability has **one** execution path. If two ways exist to do the
same thing, pick one and delete the other — do not leave parallel paths
(sourcing via JSON stdin *and* CSV, per-row CLI calls *and* batch import, etc.).

**Sourcing** (MCP export, scrape, manual list, any external fetch that
produces many rows):

1. Land the raw results in a **temporary CSV on disk** (header row + data).
   Name it predictably, e.g. `bricks/tmp/<table>-<slug>-<timestamp>.csv`
   under the workspace or project root.
2. Write to the database **only** through `db.py import-csv`, with the file
   as an explicit **positional argument** — never inlined in the conversation,
   never `--rows` JSON for a sourced mass:

   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" import-csv <table> <file.csv> [--key domain]
   ```

3. The skill's job is orchestration: source → save CSV → call `import-csv`
   with that path. Parsing, dedup, and column creation live in `db.py`.

`add --rows` stays for **small programmatic inserts** (one-off rows, transforms
inside the app) — not for sourced lead lists. The mass never lives in the
conversation.

## Rule 7 — enrichment: pass-through raw data, or batch through runner

Every enrichment action has **exactly two** valid inputs. Pick one per run —
never a third path (per-row loops in the conversation, hand-calling `agent.py`
row by row, mixing both modes on the same columns).

**A — Pass-through (user already has the values).** The user supplies raw
text or structured data (paste, file, MCP export). The skill lands it on disk
(CSV per Rule 6 when it is a mass) and writes it **as-is** into the target
columns — no AI step, no transformation. Same iron rule: the file path is an
explicit CLI argument (`import-csv`, or `modify --updates` for a small patch).

**B — Computed enrichment (values must be derived or fetched).** The skill
compiles one pipeline and delegates the whole table to `runner.py` →
`agent.py` (or a `--step` function). One command, all eligible rows, in
parallel. Obey Rule 2: preview 10 rows without `--commit` → user GO → same
command with `--commit`. Status columns are the checkpoint.

The skill never holds row-level intelligence — it only decides A vs B, frames
the target columns, and calls the right tool once.
