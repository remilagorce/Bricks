---
name: find-lookalike
description: Find companies similar to the user's best customers — "trouve des boîtes comme mes meilleurs clients", "liste lookalike". Seeds are companies rows tagged segment='seed', fed by a CRM export, a CSV or a dictated list. For the full guided motion (import, enrich seeds, analyze, source, filter) see /bricks:playbook-lookalike.
---

# Find lookalikes of the best customers

**Before anything, read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`** (§2
workspace, §3 context gate).

**Routing check first**: if the user wants the COMPLETE motion — enrich the
seeds to the maximum, discover the discriminating signal, source candidates
via FullEnrich, and filter them on that signal — hand over to
`/bricks:playbook-lookalike` instead. This skill is ONLY the
similarity-search step; used alone on bare seeds it will produce shallow
lookalikes.

Turns seed customers into a list of similar prospects. Seeds live in the
`companies` table with `segment='seed'` — ON PURPOSE: every enrichment
skill, present and future, can enrich them with a plain
`WHERE segment='seed'`, and the richer the seeds, the sharper the pattern.

## Workflow

1. **Load the seeds** — `db.py select companies --where "segment='seed'"`
   (§4). If none, ask the user ONE question: "Donne-moi 3 à 10 de tes
   meilleurs clients — nom + site si tu l'as — ou le chemin d'un CSV
   (colonnes name,domain)." Commit them per §6: a CSV goes through
   `import-csv --key domain`; a short dictated list through `db.py add
   --key domain` with `segment='seed'`, `source=dictated|csv` (no domain →
   insert only if the name is absent). A CRM export lands the same way —
   this skill never talks to a CRM itself.
2. **Understand the pattern** — read the seed rows (5-15, safe to load):
   every filled column counts (pitch, size, language, hiring… whatever
   other skills have enriched). Seeds not yet enriched: skim their sites
   (`scrape_as_markdown` if Bright Data is connected, else WebFetch).
   Derive the shared base pattern AND any discriminating signal.
   Cross-check `context/icp.md`. State it in 3-4 lines and get the user's
   confirmation BEFORE searching — a wrong pattern times 50 candidates is
   expensive noise.
3. **Search** — 3 to 5 lookalikes per seed, cap 50 per run (announce the
   scope first, §7). Queries in the seed's language: "similar to <seed>",
   "<sector> <geo> <positioning>", "alternatives à <seed>". More than 4
   seeds: delegate seed batches to subagents that append candidates to
   `bricks/tmp/find-lookalike-<date>/raw-results.jsonl` — subagents never
   touch the database.
4. **Validate and commit** — from the raw file (or directly for small
   runs): keep only candidates with a real, live website; DROP any
   candidate whose domain belongs to a seed (customers never become
   prospects); then land the survivors as a CSV and `db.py import-csv
   companies <file> --key domain` (§6), `source='lookalike:<seed-domain>'`.
   The dedup-on-insert also protects seed rows from being overwritten.
5. **Receipt** — Y seeds → X candidates (Z duplicates skipped), the
   confirmed pattern in one line, max 3 sample rows. Next step as a
   statement: "Next: `/bricks:enrich` sur les candidats — dis le mot."

## Guardrails

- Pattern confirmed by the user BEFORE any search.
- Max 5 candidates/seed, 50/run without explicit override.
- Live website required; no invented domains; seed domains dropped from
  candidates (customers never become prospects); seed rows never modified.
- No seeds and none provided → stop, suggest `/bricks:find-directory-scrape`.
