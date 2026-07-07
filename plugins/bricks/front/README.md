# front/ — the local web UI

A Clay-like table view over the current workspace's `bricks.db`, launched by the
`/bricks:interface` skill.

- `server.py` — a stdlib HTTP server (127.0.0.1 only) that reuses
  `tools/core/{workspace,db,envfile}.py`, so the UI never drifts from what the
  skills write. Run: `python3 server.py [--port 4321] [--root bricks]`.
- `index.html` — single-file React UI (table view, row selection/deletion,
  workspace switcher, ⚙ engine-keys panel). Loads React from a CDN.

The server exposes a small JSON API (`/api/status`, `/api/table/<name>`,
`/api/table/<name>/remove`, `/api/workspace/switch`, `/api/settings`). Rows are
addressed by the reserved `_id`; `_`-prefixed columns are hidden.
