# Bricks — roadmap

One block = one deliverable with a clear IN → OUT contract. A block ships
small, proves itself in real runs, then the next one starts.

## v0.1 — the core (shipped)

- `tools/core/` : workspace.py, db.py, agent.py, runner.py, session_start.py
- Skills : `find` (source companies/contacts), `enrich` (fill columns via
  runner → agent)
- MCP bundled : FullEnrich (OAuth), Bright Data (token)
- Iron gate : preview 10 rows → GO → commit, statuses as checkpoint

## Next — in order of need, not of ambition

| Block | Contract (IN → OUT) | Status |
|---|---|---|
| transform | existing table → cleaned/deduped/derived columns, zero external fetch | todo |
| score | rows + natural-language rules → score column | todo |
| front (UI) | bricks.db → local Clay-like table view (imports db.py/workspace.py directly) | todo |
| outreach | enriched rows + context/ → draft messages (draft/approved/sent statuses) | todo |
| rollback & manifests | committed run → undo (only if real runs prove the need) | todo |
| more skills from v0 (scan-mentions, find-company-people, ...) | ported one by one when a real workflow needs them | todo |

## Principles carried over from v0

- The conversation decides; files and the database carry.
- One execution path per capability — never two concurrent ways to do the
  same thing.
- Size budgets on core files (see CLAUDE.md Rule 4): growth goes into new
  steps/tools, not into the core.
