---
name: workspace-init
description: Use when the user wants to create a new Bricks workspace (a new client context, a new campaign world, or a fresh test environment), or when a brick fails because no bricks.db or tools/db.py exists in the current directory.
---

# Workspace init

Scaffold a self-contained Bricks workspace in the CURRENT directory. A
workspace is one isolated world: its own context, its own database, its own
connectors. Never initialize a workspace inside the Bricks repo itself.

## Steps

1. Safety check: if `bricks.db` or `tools/db.py` already exists here, stop and
   ask before overwriting anything. If the current directory is the Bricks
   repo (a `plugins/` directory with `.claude-plugin/` exists), refuse and ask
   the user to pick a dedicated directory (e.g. `~/bricks-workspaces/<client>/`).
2. Copy the toolchain from this plugin:
   - `${CLAUDE_PLUGIN_ROOT}/tools/db.py`  → `tools/db.py`
   - `${CLAUDE_PLUGIN_ROOT}/schema.sql`   → `tools/schema.sql`
3. Create the database: `python3 tools/db.py init`
4. Copy the workspace templates from `${CLAUDE_PLUGIN_ROOT}/templates/`:
   - `CLAUDE.workspace.md` → `CLAUDE.md`
   - `context/offer.md`, `context/icp.md`, `context/personas/decision-maker.md`
   - `mcp.json` → `.mcp.json` (FullEnrich connector — OAuth happens in the
     browser on first use, no API key to store)
5. Ask the user 3 quick questions and write the answers into `context/`:
   - What do you sell, in one sentence? (→ offer.md)
   - Who is your ideal customer? (→ icp.md)
   - Any hard disqualifiers, e.g. company size, country? (→ icp.md kill rules)
   If the user prefers to fill them later, leave the TODO placeholders.
6. Receipt: print the created tree, then tell the user the next step is
   restarting Claude Code in this directory (so CLAUDE.md and .mcp.json load)
   and running the find-fullenrich skill.

## Guardrails

- Never overwrite an existing context/ or bricks.db without explicit consent.
- Never put credentials in context/ files — connectors live in .mcp.json only.
