# Bricks

**The open-source GTM engine for Claude Code.** Find companies, enrich
contacts and work your lead lists from a conversation — your data lives in
a local SQLite database, the intelligence is your Claude subscription. No
credits, no closed spreadsheet.

## How it works

- **`tools/`** — the application: small Python scripts (workspace, db,
  agent, runner), each callable as a CLI and importable as functions.
- **`skills/`** — the instruction manuals: they tell Claude how to drive
  the tools (`find` sources companies, `enrich` fills columns row by row).
- **One workspace per client/project** — a directory holding `bricks.db`
  (the data) and `context/` (your offer, your ICP, your personas).
- **The iron gate** — every mass write is previewed on 10 rows first;
  nothing is written until you give an explicit GO.

## Quickstart

1. Install the plugin in Claude Code:
   ```
   /plugin marketplace add remilagorce/bricks
   /plugin install bricks@bricks
   ```
2. Authenticate the engine (once). Per-row enrichment runs disposable
   agents on your Claude subscription:
   ```
   claude setup-token
   ```
   then store the token in `~/.bricks/env` (chmod 600):
   ```
   CLAUDE_CODE_OAUTH_TOKEN=<token>
   BRIGHTDATA_API_TOKEN=<token>   # for web research per row
   ```
3. Open Claude Code in an empty working directory (not this repo) and ask:
   > trouve 20 agences web à Nantes

   Claude creates a workspace, sources companies and writes them to the
   database. Then:
   > enrichis la ville du siège de chaque entreprise

   Claude previews 10 rows, waits for your GO, and commits the rest.

## The rules that keep it sane

- `db.py` is the only door to the database — no raw SQL, ever.
- `runner.py` is the only loop — a pipeline of steps per row, rows in
  parallel, statuses as the checkpoint.
- Preview → GO → commit for every mass write.

## License

MIT — by Rémi Lagorce & Robin Jehanno.
