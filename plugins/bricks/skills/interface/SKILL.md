---
name: interface
description: Launch the Bricks web UI — a Clay-like table view of the current workspace's database tables, with row selection and deletion. Use when the user says "interface", "ouvre le front", "montre la table", "open the UI", "show my list".
---

# Interface

Serves the local web UI over the current workspace and gives the user a URL
to click. The UI reads the same database as the skills and deletes rows
through the same `tools/db.py` code — no divergence possible.

## Before anything: resolve the workspace

Follow the mandatory procedure in `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`:

1. `python3 "${CLAUDE_PLUGIN_ROOT}/tools/workspace.py" status`
2. Not initialized → run `init` automatically. No current workspace → create
   one (or ask) — the UI shows an empty state otherwise, which is fine too
   if the user just wants to look around.

## Launch procedure

1. **Reuse a running server if possible.** Probe the default ports:

   ```bash
   for p in 4321 4322 4323; do curl -s --max-time 1 "http://127.0.0.1:$p/api/ping"; done
   ```

   A response containing `"app": "bricks"` whose `root` matches the current
   directory's `bricks/` means the UI is already up → just give that URL.

2. **Otherwise launch it in the background** (Bash with `run_in_background`,
   from the user's project root — the server resolves `./bricks` relative to
   its cwd):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/front/server.py" --port 4321
   ```

   The server prints `Bricks UI -> http://127.0.0.1:<port>` (it scans for a
   free port if 4321 is busy). Read that line from the background task
   output, then verify with `curl -s http://127.0.0.1:<port>/api/ping`.

3. **Present the URL prominently** as the last line of your reply, e.g.:

   > Your table is live — click here: **http://127.0.0.1:4321**

   Mention that rows can be selected with the checkboxes and deleted from
   the UI, that the page auto-refreshes as skills write new data, and
   that the ⚙ button (topbar) manages the engine's API keys — stored in
   `~/.bricks/env`, values always masked (§11). When a run fails on a
   missing key, pointing the user to that panel is the friendly fix.

## Rules

- Leave the server running at the end of the turn — it is the point.
- If the user asks to stop it: find the background task or
  `pkill -f "front/server.py"`.
- The UI loads React from esm.sh (CDN) — it needs an internet connection
  the first time; if the user is offline the page will not render.
- Never touch the database outside `tools/db.py` to "help" the UI — it
  re-reads `bricks.db` on every poll (every 4 s).