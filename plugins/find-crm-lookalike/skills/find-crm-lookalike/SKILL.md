---
name: find-crm-lookalike
description: Use when the user wants to find companies similar to their best customers — e.g. "trouve-moi des boîtes comme mes meilleurs clients" or "fais-moi une liste lookalike". Seeds come from the seed_customers table, a CSV, or a dictated list; no CRM connection required.
---

# Find lookalikes of your best customers

Turn the user's best customers into a list of similar prospects. You are a
brick: seeds in, candidate companies out, receipts only. This brick is
CRM-agnostic on purpose — it reads the neutral `seed_customers` table and
never talks to a CRM itself. Contract in this plugin's BRICK.md.

## Steps

1. Verify you are in a workspace (`tools/db.py` exists), else point to
   workspace-init and stop.
2. Load the seeds:
   `python3 tools/db.py select seed_customers`
   If empty, ask ONE question: "Donne-moi 3 à 10 de tes meilleurs clients —
   nom + site si tu l'as — ou le chemin d'un CSV (colonnes name,domain)."
   Write every seed to the table: upsert by domain when a domain is given;
   otherwise check by name (`select seed_customers --where "name='<n>'"`)
   then insert. Set `source` to `dictated` or `csv`.
3. Understand the pattern. For up to 10 seeds with a domain, skim their
   websites (Bright Data `scrape_as_markdown` if available, otherwise
   WebFetch) and derive what they have in common: sector, positioning, price
   feel, size, geography, style. Cross-check with `context/icp.md` if present.
   State the pattern in 3-4 lines and get the user's confirmation BEFORE
   searching — a wrong pattern multiplied by 50 candidates is expensive noise.
4. Search the lookalikes — 3 to 5 per seed, hard cap 50 per run:
   - Prefer Bright Data `search_engine` (announce ~1 credit per query);
     otherwise use built-in web search.
   - Queries per seed: "similar to <seed>" formulations in the seed's
     language, "<sector> <geo> <positioning>" pattern queries, and
     competitor-style queries ("boutiques comme <seed>", "alternatives à
     <seed>").
   - More than 4 seeds: delegate batches of 3-4 seeds to subagents (Task
     tool, general-purpose). Each subagent runs the queries, keeps only
     candidates with a real live website, verifies the domain resolves, and
     writes rows itself:
     `python3 tools/db.py upsert companies --key domain --set domain=<d> --set name=<n> --set "source=lookalike:<seed-domain>"`
     It returns ONLY counts. Search results never enter the main conversation.
5. Filter: drop any candidate whose domain already sits in `seed_customers`
   (your customers are not prospects). Domain upserts merge duplicates with
   the existing table automatically.
6. Receipt: "Y seeds → X candidates added (Z duplicates merged). Pattern
   used: <one line>. Next: enrich-website on the new rows." Max 3 sample
   names.

## Guardrails

- Never search before the pattern is confirmed by the user.
- Max 5 candidates per seed, 50 per run, unless the user explicitly overrides.
- A candidate must have a real website; no invented or guessed domains.
- Receipts only — no search-result dumps in the conversation.
- Re-runs are safe: seeds and candidates both merge on domain.
