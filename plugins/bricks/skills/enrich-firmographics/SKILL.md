---
name: enrich-firmographics
description: Enrich companies with official firmographics — headcount, industry, SIREN, city, executives. Use when the user says "enrichis les effectifs", "ajoute la taille et le secteur", "trouve les dirigeants", "firmographics". French companies come from the official government API (free, never blocked); Bright Data only disambiguates.
---

# Enrich firmographics

Fills `employees`, `industry`, `naf`, `siren`, `city`, `executives` on
company rows. Primary source: the official French company API
(recherche-entreprises.api.gouv.fr) via `tools/firmo.py` — free, no key,
7 req/s, impossible to block. Bright Data is surgical backup only.
Contract in this directory's BRICK.md.

## Before anything

Follow `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` §2 (workspace) and §3
(context gate — if `icp.md` kill rules map to size or country, flag
matching rows in the receipt; disqualifying is the score skill's job).
No FullEnrich needed here. Bright Data (`mcp__brightdata__*`) is optional:
without it, ambiguous and non-French rows simply stay `pending` for a
later pass — say so in the receipt.

## Workflow

1. **Scope and claim** — via `db-writer` (always with the absolute
   `bricks.db` path): initialize `firmo_status='pending'` on the rows in
   scope (skip disqualified), then select up to 50 pending rows
   (`_id`, `name`, plus any locality hint available: `city`, `postal`,
   `domain`), then mark them `running`.
2. **Pass 1 — the batch lookup (free, seconds)** — write the rows as JSON
   lines (`{"_id": …, "name": …, "hint": "<city postal domain>", "siren":
   "<if already known>"}`) to `staging/firmo-<date>/input.jsonl`, then run
   ONE command:
   `python3 "${CLAUDE_PLUGIN_ROOT}/tools/firmo.py" --stdin < input.jsonl > results.jsonl`
   The tool rate-limits itself and returns one JSON per row with
   `confidence: high | ambiguous | none`. Built in: rows with a `siren`
   are looked up directly (exact match, no ambiguity), and a
   simplified-name retry (legal suffixes stripped) runs automatically
   before declaring `none`.
3. **Commit pass 1** — hand `db-writer` the `high` results in one batch:
   `employees`, `industry`, `naf`, `siren`, `city`, `executives`
   (JSON string), `firmo_status='done'` — plus `parent_company` when
   present: it means the legal representative is a COMPANY (holding /
   group), a strong "not independent" signal. Count these in the receipt
   as kill-rule candidates when the ICP wants independents. Keep the
   `ambiguous` and `none` lists for the next passes.
4. **Pass 2 — legal pages via Bright Data (~1 credit/row)** — for each
   `ambiguous` AND each French-looking `none` row (trade names are often
   not indexed by the registry — the legal name hides behind the brand):
   `scrape_as_markdown` the company's legal page
   (`https://<domain>/mentions-legales`, else find the footer link from
   the homepage). French sites must publish their SIREN/SIRET there.
   Extract it, then `firmo.py` with `"siren"` set → exact record, write
   via `db-writer` (keep the brand as `name`, store the legal identity in
   `legal_name`/`siren`).
   No SIREN found → `firmo_status='not_found'`. More than 5 ambiguous
   rows: delegate batches to subagents that write findings to
   `staging/firmo-<date>/pass2.jsonl` (they never touch the database),
   then commit via `db-writer`.
5. **Pass 3 — non-French or unmatched (`none`)** — likely foreign or
   renamed companies. Skim the site (Bright Data, else WebFetch) and
   public LinkedIn results for an employees estimate and industry; write
   them with `firmo_source='estimate'` so downstream skills know the
   grade. Never estimate `siren` or `executives` — official identifiers
   are real or absent. Nothing findable → `firmo_status='not_found'`.
6. **Close the run** — update `memory/state.json` (counts per pass),
   append one line to `NOTES.md`, receipt: "Firmographics: X done via
   official API (free), Y disambiguated via legal pages (~Y credits),
   Z estimated, W not_found. Kill-rule matches flagged: N rows under
   the size threshold." Max 3 sample rows.

## Notes for downstream bricks

- `executives` (with roles like Gérant / Président) is the direct food of
  enrich-buying-committee — for small companies the decision-maker is
  already in this column, zero extra cost. Column relay, no call.
- `employees` + `country` are the cheapest kill-rule columns: run this
  skill early, the score gate gets its early-stop material for free.
