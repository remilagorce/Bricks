# Bricks — roadmap

One block = one deliverable with a clear IN → OUT contract. A block ships
small, proves itself in real runs, then the next one starts.

## v0.1–0.2 — the core + UI (shipped)

- `tools/core/` : workspace.py, db.py, agent.py, runner.py, envfile.py,
  session_start.py
- Skills : `find`, `enrich`, `workspace`, `tools-guide`, `interface`
- Front (UI) : `front/server.py` + `index.html` — local Clay-like table view,
  row deletion and engine-keys panel, reusing the core tools directly
- MCP bundled : FullEnrich (OAuth), Bright Data (token)
- Iron gate : preview 10 rows → GO → commit, statuses as checkpoint

## Next — in order of need, not of ambition

| Block | Contract (IN → OUT) | Status |
|---|---|---|
| transform | existing table → cleaned/deduped/derived columns, zero external fetch | todo |
| score | rows + natural-language rules → score column | todo |
| outreach | enriched rows + context/ → draft messages (draft/approved/sent statuses) | todo |
| rollback & manifests | committed run → undo (only if real runs prove the need) | todo |
| more skills from v0 (scan-mentions, find-company-people, ...) | ported one by one when a real workflow needs them | todo |

## Principles carried over from v0

- The conversation decides; files and the database carry.
- One execution path per capability — never two concurrent ways to do the
  same thing.
- Size budgets on core files (see CLAUDE.md Rule 4): growth goes into new
  steps/tools, not into the core.
