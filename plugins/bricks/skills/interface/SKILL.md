---
name: interface
description: Launch the Bricks web UI — a Clay-like table view of the current workspace's database, with row selection, deletion and an engine-keys settings panel. Use when the user says "interface", "ouvre le front", "montre la table", "open the UI", "show my list".
---

# Interface — the local web UI

**Before anything, read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`** (§2 workspace).

Serves the local web UI over the current workspace and gives the user a URL to
click. The UI reads the same database as the skills and deletes rows through the
same `db.py` code path — no divergence possible.

## Resolve the workspace first

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/workspace.py" status
```

No current workspace → create one (`new <name>`) or ask. The UI also shows a
clean empty state, which is fine if the user just wants to look around.

## Launch procedure

1. **Reuse a running server if possible.** Probe the default ports:

   ```bash
   for p in 4321 4322 4323; do curl -s --max-time 1 "http://127.0.0.1:$p/api/ping"; done
   ```

   A response `{"app": "bricks", ...}` whose `root` matches the current
   directory's `bricks/` means the UI is already up → just give that URL.

2. **Otherwise launch it in the background** (Bash with `run_in_background`,
   from the user's project root — the server resolves `./bricks` from its cwd):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/front/server.py" --port 4321
   ```

   The server prints `Bricks UI -> http://127.0.0.1:<port>` (it scans for a free
   port if 4321 is busy). Read that line from the background task output, then
   verify with `curl -s http://127.0.0.1:<port>/api/ping`.

3. **Present the URL prominently** as the last line of your reply, e.g.:

   > Your table is live — click here: **http://127.0.0.1:4321**

   Mention that rows can be selected and deleted from the UI, that the page
   auto-refreshes as skills write new data, and that the ⚙ button manages the
   engine's API keys (stored in `~/.bricks/env`, values always masked). When a
   run fails on a missing key, that panel is the friendly fix.

## Rules

- Leave the server running at the end of the turn — it is the point.
- To stop it: find the background task or `pkill -f "front/server.py"`.
- The UI loads React from a CDN — it needs an internet connection the first
  time; offline, the page will not render.
- Never touch the database outside `db.py` to "help" the UI — it re-reads
  `bricks.db` on every poll.
