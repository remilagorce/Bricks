---
name: playbook-lookalike
description: Use when the user wants the complete lookalike motion — "construis-moi une liste lookalike depuis mes meilleurs clients", importing best customers from a CRM/CSV/list, enriching them, finding what they share, then sourcing and filtering similar companies. Composes other bricks; for the search step alone, see find-crm-lookalike.
---

# Playbook: full lookalike motion

You are the orchestrator following a recipe. You do NOT do the work yourself —
you chain bricks through the table, phase by phase, and keep the user in the
loop at the two decision points (pattern confirmation, filter confirmation).
Composition rationale in this plugin's PLAYBOOK.md.

## Phase 1 — Import the winners (→ segment='seed')

Ask where the best customers live. Route by what the user provides:
- A CRM credential or URL → detect the system from its shape (HubSpot tokens
  start with `pat-`, Notion secrets with `ntn_`/`secret_`, a Notion URL is a
  notion.so link, Salesforce is an OAuth org URL…). If a matching
  crm-import brick or MCP connector is available in this workspace, use it;
  if not, say so honestly and fall back to CSV/dictated — never fake a CRM
  connection.
- A CSV path (columns name,domain) → import it.
- A dictated list → write it.
Every seed row: `python3 tools/db.py upsert companies --key domain --set domain=<d> --set name=<n> --set segment=seed --set source=<crm|csv|dictated>`
Target 5-15 seeds. Receipt: count + the Lookalike tab of the viewer.

## Phase 2 — Enrich the seeds with EVERY relevant brick

List the enrichment skills actually installed (enrich-website,
enrich-company-*…). Run each relevant one scoped to the seeds — every
enrichment brick accepts a narrower scope, use:
`WHERE segment='seed' AND <col>_status='pending'`
Do NOT hardcode a brick list: discover what exists at runtime, so bricks
installed next week automatically join this pass. Skip paid person-level
bricks (emails) — useless for pattern analysis. Receipt per brick.

## Phase 3 — Analyze: what do the winners share?

Read the enriched seed rows (5-15 rows — small, safe to load). Compare every
filled column: sector, positioning, size, geography, language, style, and
any signal columns present (hiring, tech stack… as those bricks ship).
Produce:
- the shared base pattern (3-4 lines),
- the DISCRIMINATING signal(s) — what these winners have that average
  companies do not ("ils recrutent tous un manager").
Present both to the user and get confirmation. This is the moment that
decides everything downstream — do not rush it.

## Phase 4 — Source candidates

Pick the sourcing brick(s) that fit the confirmed pattern and run them:
- find-crm-lookalike for similarity search from the seeds,
- find-fullenrich when the pattern maps to firmographic filters
  (industry, size, geography),
- find-directory-scrape when an obvious directory covers the segment.
Cap the combined total at ~100 candidates without explicit override.

## Phase 5 — Filter on the discriminating signal

Re-run ONLY the discriminating enrichment brick(s) on the candidates,
cheapest first (early-stop thinking: never enrich everything). Then:
- candidates matching the signal → keep (they are the lookalike list),
- others → leave as ordinary prospects (do not delete — they may serve
  another campaign).
Final receipt: seeds used, pattern, signal, candidates sourced, candidates
matching, next step (enrich-email or write-sequence on the matches).

## Guardrails

- Two mandatory user checkpoints: after Phase 3 (pattern + signal) and
  before any paid enrichment in Phase 5 (volume + cost).
- Never fake a CRM connection; degrade honestly to CSV/dictated.
- Receipts between phases — never dump rows (exception: the 5-15 seed rows
  in Phase 3, which are the analysis material).
- Each phase is resumable: statuses tell you where the previous run stopped.
