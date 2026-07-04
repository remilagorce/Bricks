---
name: find-crm-lookalike
description: Use when the user wants to find companies similar to their best customers — e.g. "trouve-moi des boîtes comme mes meilleurs clients" or "fais-moi une liste lookalike". Seeds are companies rows tagged segment='seed' (from a CRM import brick, a CSV, or a dictated list). For the full guided motion (import, enrich seeds, analyze, source, filter), see playbook-lookalike.
---

# Find lookalikes of your best customers

Turn seed customers into a list of similar prospects. You are a brick: seeds
in, candidate companies out, receipts only. Seeds live in the companies table
(`segment='seed'`) so any enrichment brick can enrich them beforehand — the
richer the seeds, the sharper the pattern. Contract in this plugin's BRICK.md.

## Steps

1. Verify you are in a workspace (`tools/db.py` exists), else point to
   workspace-init and stop.
2. Load the seeds:
   `python3 tools/db.py select companies --where "segment='seed'"`
   If empty, ask ONE question: "Donne-moi 3 à 10 de tes meilleurs clients —
   nom + site si tu l'as — ou le chemin d'un CSV (colonnes name,domain)."
   Write each seed:
   `python3 tools/db.py upsert companies --key domain --set domain=<d> --set name=<n> --set segment=seed --set source=dictated`
   (no domain → check by name first, then insert with segment=seed).
3. Understand the pattern. Read EVERYTHING the seed rows already contain —
   pitch, language, size_hint and any column other bricks have filled. For
   seeds whose `website_status` is still pending, skim their sites (Bright
   Data `scrape_as_markdown` if available, else WebFetch). Derive what the
   winners share: sector, positioning, price feel, size, geography, style —
   and any discriminating signal present in the data. Cross-check with
   `context/icp.md`. State the pattern in 3-4 lines and get the user's
   confirmation BEFORE searching — a wrong pattern times 50 candidates is
   expensive noise.
4. Search the lookalikes — 3 to 5 per seed, hard cap 50 per run:
   - Prefer Bright Data `search_engine` (announce ~1 credit per query),
     otherwise built-in web search.
   - Queries per seed, in the seed's language: "similar to <seed>"
     formulations, "<sector> <geo> <positioning>" pattern queries,
     competitor-style queries ("boutiques comme <seed>", "alternatives à
     <seed>").
   - More than 4 seeds: delegate batches of 3-4 seeds to subagents (Task
     tool, general-purpose). Each subagent runs the queries, keeps only
     candidates with a real live website, and writes rows itself:
     `python3 tools/db.py upsert companies --key domain --set domain=<d> --set name=<n> --set "source=lookalike:<seed-domain>"`
     It returns ONLY counts. Search results never enter the main conversation.
5. Protection of seeds: before any candidate upsert, drop it if its domain
   belongs to a seed row — customers never become prospects, and an upsert
   must never overwrite a seed.
6. Receipt: "Y seeds → X candidates added (Z duplicates merged). Pattern
   used: <one line>. Next: enrich-website on the new rows — or the
   discriminating-signal filter if you ran playbook-lookalike." Max 3 sample
   names.

## Guardrails

- Never search before the pattern is confirmed by the user.
- Max 5 candidates per seed, 50 per run, unless the user explicitly overrides.
- A candidate must have a real website; no invented or guessed domains.
- Receipts only — no search-result dumps in the conversation.
- Re-runs are safe: seeds and candidates both merge on domain.
