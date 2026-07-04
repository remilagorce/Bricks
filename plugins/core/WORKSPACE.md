# Workspace layout — the world a brick lives in

FROZEN CONTRACT. A workspace is one directory = one client context = one
isolated world. Bricks assume this exact layout, relative to the current
working directory:

```
<workspace>/
├── CLAUDE.md              identity + golden rules, auto-loaded every session
├── bricks.db              the SQLite database (THE bus between bricks)
├── .mcp.json              external connectors for THIS workspace (FullEnrich…)
├── context/               the client brain — human-editable
│   ├── offer.md           what we sell, proof points, tone
│   ├── icp.md             ideal customer profile + kill rules
│   └── personas/          one file per buyer persona
└── tools/
    ├── db.py              the single write door to bricks.db
    └── schema.sql
```

Rules:
- A brick NEVER reads or writes outside the workspace it runs in.
- All database access goes through `python3 tools/db.py …` — no raw sqlite3.
- Credentials live in the workspace (`.mcp.json`, env), never in the repo.
- Workspaces are data, not code: never commit a real workspace to git.

To create a workspace: run the `workspace-init` skill from the core plugin.
