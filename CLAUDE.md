# Bricks — project rules

Bricks is an open-source, Claude-native alternative to Clay: GTM workflows
(find, enrich, transform, scan...) composed from granular bricks that read
and write a per-workspace SQLite database, instead of paying per credit in
a closed spreadsheet.

## Structure

```
.claude-plugin/marketplace.json   # the marketplace: lists the "bricks" plugin
plugins/bricks/
  .claude-plugin/plugin.json      # plugin manifest
  .mcp.json                       # bundled MCP servers (fullenrich, ...)
  CONVENTIONS.md                  # the shared contract every skill follows
  skills/                         # GTM bricks (see rule below)
    workspace/SKILL.md            #   create/switch/list workspaces
    find/SKILL.md                 #   source companies & contacts
    enrich/SKILL.md               #   fill columns on existing rows
    transform/SKILL.md            #   clean/dedupe/score/filter tables
    scan-mentions/SKILL.md        #   answer one question about a site
    interface/SKILL.md            #   launch the local web UI
  agents/
    db-writer.md                  # the only agent allowed to touch bricks.db
  tools/
    workspace.py                  # workspace lifecycle (bricks/config.json)
    db.py                         # the only door to bricks.db (used by db-writer)
    session_start.py              # SessionStart hook: injects workspace banner
  front/                          # local web UI (server.py + index.html)
  templates/context/              # scaffolded into new workspaces (offer.md, icp.md, personas/)
```

## Rule 1 — GTM bricks live in `skills/`

Every GTM capability (finding, enriching, transforming, scanning...) is a
`SKILL.md` under `plugins/bricks/skills/`. A brick is never a standalone
script the user runs by hand, and never logic buried in `tools/`: `tools/`
holds only the plumbing (workspace lifecycle, database access) that skills
call into. When adding a new brick, add a new skill directory — do not grow
an existing skill to cover an unrelated capability.

## Rule 2 — database writes go through the `db-writer` agent

No skill calls `tools/db.py` itself. Every read and write to `bricks.db` is
delegated, in natural language, to the `db-writer` subagent
(`plugins/bricks/agents/db-writer.md`): "insert these rows, dedup on
domain", "claim 25 pending rows", "write employees=120 for id 3".

`db-writer` is the single place that holds `db.py`'s exact CLI contract.
That is deliberate: a `SKILL.md` describing a tool's flags in prose is a
contract that can silently drift from the tool's real interface as it
evolves. Centralizing that knowledge in one agent means only one file to
keep in sync with `tools/db.py` — not every skill that touches data. See
`CONVENTIONS.md` §5 for the full status vocabulary and iron rules
`db-writer` enforces (mark `running` before working, write immediately,
never dump raw tables into the conversation).

## Running things end to end

Two ways to chain bricks into a full pipeline (e.g. find → enrich →
transform):

1. **Natural language, turn by turn** — just tell Claude what you want
   ("trouve des entreprises SaaS en France, puis enrichis leurs emails").
   Claude reads each skill's `description`, decides which brick matches
   the current step, and runs it — no setup needed. Best for exploration,
   one-off requests, or when the next step depends on what the previous
   one found.
2. **A workflow** — a fixed sequence you want to repeat identically. A
   workflow names, in order, the **agents** to call (not the skills
   directly) and what to hand each one. An agent wraps a skill for
   isolated, repeatable execution: add `context: fork` (+ `agent:` if you
   want a specific executor, otherwise `general-purpose`) to a skill's
   frontmatter to make it callable as a self-contained unit that returns
   only a summary, not its full execution trace. Use a workflow when the
   steps and their order are already known and shouldn't be re-decided
   every run.

## Dispatch vs automatic delegation

This is the difference between the two ways above, and it matters when you
write a workflow:

- **Automatic delegation** — Claude reads the `description` of every
  available skill/agent and *decides* which one matches your request. Non
  deterministic by design: good for natural language, wrong tool for a
  pipeline you need to run the same way every time (Claude could match a
  different skill if you phrase a step differently).
- **Dispatch (explicit invocation)** — you (or a workflow) name the exact
  agent to run, by name (`@db-writer`, `@find`, ...), instead of letting
  Claude choose. Deterministic: the same workflow step always calls the
  same agent. Workflows should dispatch explicitly, step by step, rather
  than describing steps in prose and hoping Claude picks the right skill
  each time.

In short: natural language conversation → automatic delegation is fine.
A workflow you want to trust and re-run → dispatch explicitly.

## Rule 3 — bump the version on every plugin change

Installed plugins are cached BY VERSION: if `plugins/bricks/` changes but
`version` stays the same, `claude plugin update` answers "already at latest"
and every session keeps running the stale cache — silently. Any change under
`plugins/bricks/` ships with a version bump in BOTH
`plugins/bricks/.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json`, then `claude plugin update bricks@bricks`
and a session restart. (This bug cost us two test sessions running a plugin
from before the merge.)
