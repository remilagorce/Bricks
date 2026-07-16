---
name: find-gmaps
description: Source local businesses from Google Maps searches via Bright Data — one keyword crossed with one or more locations ("tous les courtiers assurance à Lyon et Bordeaux") → verified website domains written into the current Bricks workspace database. Use for "recherche google maps", "scrape google maps", "trouve les <métier> à <ville>", local/niche commerce that B2B databases cover poorly.
context: fork
agent: general-purpose
---

# Find via Google Maps (Bright Data dataset)

Turns Google Maps queries into `companies` rows with verified domains.
The heavy lifting is one deterministic tool — `tools/gmaps.py` (Bright
Data's Google Maps dataset, `discover_new` by location) — never the
session iterating places. Contract in this directory's BRICK.md.

## Before anything: resolve the workspace and read the context

Follow the mandatory procedure in `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`
(§2 workspace resolution, §3 context gate and drift guardrail).

**Token gate** — the tool self-loads `BRIGHTDATA_API_TOKEN` from
`~/.bricks/env`. If its receipt says the token is absent, ask the user to
paste it (provider key — chat is fine, §5) and store it with
`python3 "${CLAUDE_PLUGIN_ROOT}/tools/envfile.py" set BRIGHTDATA_API_TOKEN <token>`,
then re-run. No MCP needed: this lane is pure HTTP.

## Workflow

1. **Input** — a keyword (métier/activité) and one or more locations, or
   ready-made queries. Vague request → default to the workspace ICP.
   Write the agreed criteria to `memory/NOTES.md`.
2. **Announce the plan** (money gate, §8): every record returned is
   METERED by Bright Data, so `--limit` is the spend cap — announce
   `queries × limit` as the worst case. Default `--limit 50` per query;
   above the big-spend threshold → ONE grouped GO.
3. **Run the tool** — output goes to the workspace staging area:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/gmaps.py" \
     --keyword "courtier assurance" --locations "lyon, bordeaux" \
     --limit 50 --out <ws>/staging/find-gmaps-<YYYY-MM-DD>/domains.csv
   ```

   (`--queries "…" "…"` for ready-made queries.) The tool writes the
   provisional CSV (deduped on domain, platform links and closed places
   dropped) and prints the WHOLE file on stdout — this skill runs forked,
   so that dump lands in the fork's disposable context, never the
   session's (§10). What you act on is the JSON receipt on stderr.
   **Record the `snapshot_id`** (stderr, printed at submit time) in
   `memory/state.json` immediately: an interrupted run resumes with
   `--snapshot <id>` instead of paying twice (§8.5).
4. **Commit to the database** (CONVENTIONS §5):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" import-csv companies \
     <ws>/staging/find-gmaps-<date>/domains.csv --key domain --db <bricks.db>
   ```

   `--key domain` dedups against rows already in base; the receipt says
   how many were inserted vs skipped.
5. **Delete the provisional CSV** — after a SUCCESSFUL import only:
   `rm` the file (and its run directory if empty). The database is the
   checkpoint; the CSV was a staging artifact, not a ledger. Import
   failed → KEEP the file, report the error, do not retry blindly.
6. **Close the run** — update `memory/state.json` (queries covered,
   snapshot_id, spend), append a summary line to `NOTES.md`, report the
   receipt: X places fetched, Y domains imported, Z duplicates skipped,
   dropped counts (closed / no site / platform link), wall-time. Max 3
   sample rows in the chat — the data lives in the database.
