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

## v0.3 — the v0 port (shipped)

Everything proven in v0 (clay-gtm-agent), adapted to this repo's contract
(tools/core + steps, one execution path, CSV sourcing, iron gate):

- `tools/providers/` : firmo.py (+ runner step), fullenrich.py (runner
  step, child-row inserts), jobs.py (hunt/check), news.py — deterministic,
  zero model, zero db
- `tools/core/agent_api.py` : Messages-API transport for agent.py
  (`BRICKS_AGENT_TRANSPORT=api`) — for machines where the SDK stack can't
  run (Bun requires AVX)
- Skills : transform, score (+ kernel/materialize scripts, judge via
  agent.py), rank-accounts (+ frozen kernel), scan-mentions,
  find-lookalike, find-directory-scrape, find-hiring-signal,
  find-company-people, enrich-firmographics, enrich-buying-committee,
  enrich-person-profile, signal-person, plan-outreach, write-outreach,
  playbook-lookalike, playbook-outbound, context-write — the v0 BRICK.md
  contracts folded into each SKILL.md; gtm-onboard/brickgent plumbing
  repaired

## Next — in order of need, not of ambition

| Block | Contract (IN → OUT) | Status |
|---|---|---|
| outreach-send | approved drafts → sent emails (human-gated) | todo |
| rollback & manifests | committed run → undo (only if real runs prove the need) | todo |

## Principles carried over from v0

- The conversation decides; files and the database carry.
- One execution path per capability — never two concurrent ways to do the
  same thing.
- Size budgets on core files (see CLAUDE.md Rule 4): growth goes into new
  steps/tools, not into the core.
