# Bricks — project log

Living document: validated architecture, decisions, how to run the current
state. Update it when a structural decision lands.

## What Bricks is

Open-source GTM engine, Claude-native. Granular bricks (Claude Code plugins)
compose any GTM scenario — like Clay's columns, but open, local-first, and
driven by an agent on the user's own Claude subscription.

- Star topology: bricks read/write columns of a per-workspace SQLite database
  (`bricks.db`) and never call each other. Handoff = WHERE clauses on statuses.
- Workspace = one directory = one isolated client context (`context/`,
  database, connectors). Physical context isolation — no cross-client leakage.
- Context economy: bulk data is written by scripts and subagents straight to
  the database; the main conversation only carries receipts.

## v0 scope (branch `v0-first-bricks`) — the steel thread

| Piece | What it does |
|---|---|
| `plugins/core` | Frozen contract: `schema.sql`, `STATUSES.md`, `WORKSPACE.md`, `tools/db.py`, `workspace-init` skill + workspace templates |
| `plugins/find-fullenrich` | Source companies + contacts via FullEnrich search (MCP, OAuth) |
| `plugins/enrich-website` | Visit each site → `pitch`, `language`, `size_hint` |
| `plugins/enrich-email` | Verified emails via FullEnrich (paid, volume confirmed first) |
| `plugins/write-sequence` | 3-email personalized sequence per contact → `messages` (drafts) |

The chain to demo: find-fullenrich → enrich-website → enrich-email →
write-sequence, run by hand from a Claude Code session inside a workspace.

## v0 simplifications (deliberate, upgrade later without breaking bricks)

- Fixed columns in the schema — the dynamic column registry (columns/cells)
  comes later.
- No orchestrator, no playbooks — the human chains bricks manually.
- No cockpit UI — inspect the table with `python3 tools/db.py show`.
- No scoring bricks yet — kill rules are documented in icp.md but only flagged.
- Shared subagent definitions not extracted yet — enrich-website uses the
  built-in general-purpose subagent with an inline mission.

## Key decisions

1. Bricks are plugins, max granularity, contracts in BRICK.md (IN/OUT =
   columns + statuses). Chosen for parallel team work and Clay-like modularity.
2. `db.py` is the single write door; WAL mode; statuses give idempotence.
3. FullEnrich MCP is declared per workspace (`.mcp.json`), OAuth in browser —
   no API keys stored anywhere.
4. Workspaces are data, never committed. `workspace-init` scaffolds them
   self-contained (tools copied in), so bricks have zero install-path coupling.
5. Repo language: English (skills, docs, contracts). Conversation with users
   can be any language.

## How to run (v0)

```bash
# 1. In Claude Code, from any directory:
/plugin marketplace add /path/to/Bricks     # or remilagorce/Bricks once merged
/plugin install core@bricks find-fullenrich@bricks enrich-website@bricks enrich-email@bricks write-sequence@bricks

# 2. Create a workspace OUTSIDE the repo:
mkdir -p ~/bricks-workspaces/demo && cd ~/bricks-workspaces/demo
claude                       # start a session here
# → run the workspace-init skill, answer the 3 context questions
# → restart claude here (loads workspace CLAUDE.md + .mcp.json)

# 3. The steel thread:
# → find-fullenrich    (preview free, confirm volume)
# → enrich-website     (free)
# → enrich-email       (PAID — confirms volume first)
# → write-sequence     (drafts only)
python3 tools/db.py show     # the table tells the whole story
```

Offline test without FullEnrich: `python3 tools/db.py seed --csv fixtures/seed_companies.csv`
(from a workspace, with the CSV copied in) then run enrich-website on real
domains only.

## Next (post-v0 backlog)

- Kill/score bricks (`score-killer-gate`, `score-icp-fit`) + scoring.yaml.
- Extract shared subagents (web-researcher, copywriter) into core.
- Send/outreach bricks with approval flow + PreToolUse guard hook.
- Dynamic column registry, then the cockpit (tabs = workspaces, live table).
- CI: validate plugin manifests + BRICK.md presence on every PR.
