# Bricks — project rules

Bricks is an open-source, Claude-native alternative to Clay: GTM workflows
(find, enrich, transform, scan...) backed by a per-workspace SQLite database,
driven from Claude Code.

## The architecture, in one sentence

`tools/core/` is the engine (workspace, db, runner, agent — plain Python,
every script callable BOTH as a CLI and as importable functions);
`tools/providers/` are deterministic provider adapters that plug into the
runner as steps; `skills/` are the instruction manuals that tell the AI how
to act and how to drive the application through those tools.

**Two audiences, two contracts.** This `CLAUDE.md` is for whoever *builds and
maintains* the repo. `plugins/bricks/CONVENTIONS.md` is the *runtime* contract
every skill reads before acting; `/bricks:tools-guide` is the on-demand
tool-by-tool reference (both call modes). Keep CONVENTIONS.md short — when a
rule outgrows a few lines it belongs in a tool or a skill, not there. The
Bricks root is created lazily on the first GTM action (`workspace.py new`);
the SessionStart hook only REPORTS state — it never creates anything.

## Rule 1 — logic lives in tools, never in skills

A new need = a new **provider** or a new **skill**, never code buried in the
core or in a SKILL.md. Always reuse the existing functions first; anything
reusable goes to `tools/`, a script truly specific to one skill lives in that
skill's `scripts/`. Never hand-write SQL in the conversation.

The core files and their single responsibilities:

- `tools/core/workspace.py` — workspace lifecycle. One directory per
  workspace (`bricks/workspaces/<slug>/`), one pointer (`bricks/config.json`).
- `tools/core/db.py` — the ONLY door to a workspace database. Dynamic
  tables/columns (Clay-style), `_id` reserved, atomic `claim`, JSON receipts.
  Called DIRECTLY with Bash — no subagent in between: db.py is deterministic
  and injection-safe, a delegation layer only adds a model round-trip per
  call (per-row dispatches were the single biggest slowness of Bricks 1).
  Write waves in ONE call (`modify --updates '[...]'`), never one call per row.
- `tools/core/agent.py` — the single AI-calling function: one prompt, one
  answer, optional Bright Data web research, optional guaranteed JSON schema
  output. Subscription by default; `BRICKS_AGENT_TRANSPORT=api` for machines
  where the SDK cannot run (API credits).
- `tools/core/runner.py` — THE loop: a pipeline of steps per row (each with
  its own JSON args, `--ai` always last), rows in parallel, claims by
  tranches, wave writes, run-id + manifest + rollback. Zero intelligence.

## Rule 2 — preview before any mass write (the iron gate)

Every bulk action runs `runner.py run … --preview 10` first: the 10 pilot
rows are computed, WRITTEN tagged with the run-id, and streamed live (NDJSON
on stderr — relay them; the user checks the interface). ONE explicit GO; only
then `--commit` processes the mass (preview rows are settled, never re-paid).
Statuses (`pending/running/done/not_found/failed` in a `X_status` column) are
the checkpoint — re-running resumes, `release` frees crashed rows,
`--retry-failed` is the explicit retry, `rollback --manifest` erases a run.

## Rule 3 — bump the version on every plugin change

Installed plugins are cached BY VERSION: if `plugins/bricks/` changes but the
version stays the same, `claude plugin update` answers "already at latest"
and sessions silently run the stale cache. Any change under `plugins/bricks/`
ships with a version bump in BOTH `plugins/bricks/.claude-plugin/plugin.json`
and `.claude-plugin/marketplace.json`, then `claude plugin update
bricks@bricks` and a session restart.

## Rule 4 — stay small, grow sideways

The core is complete: it grows for RAILS (safety, bookkeeping), not for
features. A new capability is a provider step, a skill, or a ROADMAP line —
never a new branch in the core loop. If two ways exist to do the same thing,
pick one and delete the other — no parallel paths.

## Rule 5 — skills: official tooling, slash-command references

When creating or rewriting a skill under `plugins/bricks/skills/`, use the
official Claude skill tooling (skill-creator / plugin-dev) — do not improvise
structure: precise trigger description, short body, `references/` for depth,
`scripts/` for deterministic code, zero useless files.

Whenever a skill, doc, or handoff mentions another Bricks skill, write it as
a slash command — `/bricks:<skill-directory-name>` — never a file path.

## Rule 6 — one logical pipeline; sourcing goes through a CSV file

Sourcing (MCP export, scrape, manual list — any external fetch producing many
rows): land the raw results in a CSV on disk, then
`db.py import-csv <table> <file.csv> --key <col>`. The skill's job is
orchestration: source → save CSV → import. Parsing, dedup and column creation
live in `db.py`. `add --rows` stays for small programmatic inserts — never
for a sourced mass. The mass never lives in the conversation.

## Rule 7 — enrichment: pass-through raw data, or batch through runner

Exactly two valid inputs per enrichment run — (A) pass-through: the user
already has the values, land them and write as-is (`import-csv` / small
`modify`); (B) computed: compile ONE pipeline and delegate the whole table to
`runner.py` (steps and/or `--ai` → `agent.py`), preview → GO → commit. Never
a third path: no per-row loops in the conversation, no hand-calling
`agent.py` row by row (≲5 dictated rows are `/bricks:brickgent`'s in-session
regime). The skill never holds row-level intelligence — it decides A vs B,
frames the columns, and calls the right tool once.

## Rule 8 — workflows dispatch explicitly

Natural-language conversation → automatic delegation (Claude matches the
skill by its description) is fine. A playbook or workflow you want to trust
and re-run → it names the exact skills to invoke, in order (`/bricks:enrich`
then `/bricks:score` …), step by step — never prose descriptions hoping
Claude picks the right brick each time. Deterministic beats clever.
