---
name: playbook-lookalike
description: The complete lookalike motion — import best customers from any source (CRM export, CSV, dictated list), enrich them with every available skill, find what the winners share, then source and filter similar companies on the discriminating signal. "Construis-moi une liste lookalike depuis mes meilleurs clients." For the search step alone, see /bricks:find-lookalike.
---

# Playbook: full lookalike motion

**Before anything, read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`** (§2
workspace, §3 context gate).

You are the orchestrator following a recipe: you chain skills through
the database, phase by phase, with the user at the two decision points.
You do not hardcode which skills exist — you discover what is installed
at runtime, so capabilities added next week join this motion
automatically.

## Phase 1 — Import the winners (→ segment='seed')

Ask where the best customers live, and route on what the user provides:

- a CRM credential or URL → detect the system from its shape (HubSpot
  tokens start with `pat-`, Notion secrets with `ntn_`/`secret_`, a
  notion.so URL, a Salesforce org URL…). If a matching connector is
  available in this workspace, use it; otherwise SAY SO honestly and
  fall back — never fake a CRM connection. A CSV export from any CRM
  works today.
- a CSV path → `db.py import-csv companies <file> --key domain` (§6); a
  dictated list → `db.py add --key domain`. Both with `segment='seed'`,
  `source=<crm|csv|dictated>`.

Target 5-15 seeds. Receipt.

## Phase 2 — Enrich the seeds with EVERY relevant skill

List the enrichment skills actually installed
(`/bricks:enrich-firmographics`, `/bricks:enrich`, …). Run each relevant
one scoped to the seeds (`WHERE segment='seed'`). Skip paid person-level
enrichments (emails) — useless for pattern analysis, and the cost
doctrine (§7) exists for a reason. Receipt per skill.

## Phase 3 — Analyze: what do the winners share?

Read the enriched seed rows (5-15 — safe to load; this is the one
authorized exception to "no rows in the conversation", they ARE the
analysis material). Compare every filled column. Produce: the shared
base pattern (3-4 lines) AND the discriminating signal(s) — what these
winners have that average companies do not ("ils recrutent tous un
manager"). Present both, get explicit confirmation. This checkpoint
decides everything downstream — never skip it.

## Phase 4 — Source candidates

Pick the sourcing skill(s) that fit the confirmed pattern:
`/bricks:find-lookalike` (similarity from seeds), `/bricks:find`
(FullEnrich firmographic filters — industry, size, geography),
`/bricks:find-directory-scrape` (when an obvious directory covers the
segment). Cap the combined total at ~100 candidates without an explicit
override.

## Phase 5 — Filter on the discriminating signal

Re-run ONLY the discriminating enrichment skill(s) on the candidates,
cheapest first — never enrich everything (early-stop thinking + the cost
doctrine). Candidates matching the signal → the lookalike list. Others →
stay as ordinary prospects for another campaign; do not delete.

Final receipt: seeds, pattern, signal, sourced, matching, and the next
step as a statement (`/bricks:enrich` emails then
`/bricks:write-outreach` on the matches). The statuses and `segment`
columns are the checkpoints — an interrupted motion resumes from the
database's state.
