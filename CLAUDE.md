# Bricks — repo conventions

Bricks is an open-source GTM engine: granular bricks (Claude Code plugins)
that read and write columns of a per-workspace SQLite database. Star topology:
bricks NEVER call each other; the table is the bus.

## Architecture rules (enforced in review)

1. One brick = one plugin under `plugins/<brick-name>/` with `.claude-plugin/plugin.json`,
   `BRICK.md` (the IN/OUT contract), and `skills/<brick-name>/SKILL.md`.
2. Bricks depend only on the workspace contract defined by `plugins/core/`
   (schema.sql, STATUSES.md, WORKSPACE.md). Never on another brick.
   Brick-to-brick handoff = a WHERE clause on statuses, nothing else.
3. All database access goes through `tools/db.py` in the workspace. No raw sqlite3.
4. Data flows through the database, never through the conversation: bricks
   report receipts (counts), max 3 sample rows.
5. Paid actions (FullEnrich, any credit-consuming API) announce volume and get
   explicit user confirmation first. Messages are always `draft`; only humans approve.
6. `plugins/core/` is the FROZEN CONTRACT: changes require a PR approved by
   the whole team. Everything else moves fast.

## Working agreements

- One brick = one branch (`brick/<name>`) = one PR = one person. Never two
  people in the same brick folder.
- Never commit workspaces, databases or credentials (see .gitignore).
- Skills and docs are written in English; keep SKILL.md descriptions in the
  "Use when…" form so triggering stays sharp.
- Test a brick by scaffolding a throwaway workspace with the `workspace-init`
  skill (from `plugins/core`), then running the brick against fixtures/seed data.
