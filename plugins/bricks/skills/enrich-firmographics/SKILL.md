---
name: enrich-firmographics
description: Enrich companies with official firmographics — headcount, industry, SIREN, city, executives. Use when the user says "enrichis les effectifs", "ajoute la taille et le secteur", "trouve les dirigeants", "firmographics". French companies come from the official government API (free, never blocked); Bright Data only disambiguates.
---

# Enrich firmographics

**Before anything, read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`** (§2
workspace, §3 context gate — if `icp.md` kill rules map to size or
country, flag matching rows in the receipt; disqualifying is
`/bricks:score`'s job).

Fills `employees`, `industry`, `naf`, `siren`, `city`, `executives` on
company rows. Primary source: the official French company API
(recherche-entreprises.api.gouv.fr) via `tools/providers/firmo.py` —
free, no key, 7 req/s, impossible to block. Bright Data is surgical
backup only; without it, ambiguous and non-French rows simply stay
`pending` for a later pass — say so in the receipt.

## Pass 1 — the engine lane (free, deterministic, iron gate §5)

One runner pipeline, the firmo step doing the per-row lookup:

```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/runner.py" --table companies \
  --step "${CLAUDE_PLUGIN_ROOT}/tools/providers/firmo.py:step" \
  --status-col firmo_status
```

Preview (no `--commit`): first 10 rows computed, shown, NOTHING written.
The step reads `name` (+ `hint`/`city`/`postal`/`domain`, and `siren`
when already known — exact match, no ambiguity; a simplified-name retry
runs automatically before declaring `none`) and returns
`firmo_confidence: high | ambiguous | none` plus the columns. ONE GO →
`--commit` on the whole scope (`--where` to skip disqualified rows).
Statuses are the checkpoint; re-running resumes pending rows. The tool
rate-limits itself under the API's 7 req/s.

**Group detection, two complementary signals** (flag in the receipt as
kill-rule candidates when the ICP wants independents; never disqualify
without user confirmation):

- `parent_company` set → directly controlled (e.g. président = a
  holding);
- `company_category` is GE or ETI while local `employees` is small →
  INSEE computes the category at GROUP level: a "10-19 employees GE" is
  a subsidiary (e.g. traqfood → Mérieux NutriSciences). Confirm the
  parent with a quick web check before flagging by name.

## Pass 2 — legal pages via Bright Data (~1 credit/row), ONE wave

Scope: every `ambiguous` AND every French-looking `none` row (trade
names are often not indexed by the registry — the legal name hides
behind the brand). Scrape ALL their legal pages in one `scrape_batch`
call (`https://<domain>/mentions-legales` for each; misses retried via
the footer link from the homepage, again batched). French sites must
publish their SIREN/SIRET there. Extract them, write the found `siren`
values onto the rows (`db.py modify --updates`, one batch), then re-run
the SAME runner command — rows are re-eligible once their
`firmo_status` is reset to `pending` in that same batch; the step's
siren path returns exact records (keep the brand as `name`, store the
legal identity in `legal_name`/`siren`). No SIREN found →
`firmo_status='not_found'`. Beyond ~40 such rows: subagent batches,
findings to `bricks/tmp/firmo-<date>/pass2.jsonl` (they never touch the
database), then commit via `db.py`.

## Pass 3 — non-French or unmatched (`none`)

Likely foreign or renamed companies. Skim the site (Bright Data, else
WebFetch) and public LinkedIn results — all rows' fetches in one wave —
for an employees estimate and industry; write them with
`firmo_source='estimate'` so downstream skills know the grade. Never
estimate `siren` or `executives` — official identifiers are real or
absent. Nothing findable → `firmo_status='not_found'`.

## Receipt

"Firmographics: X done via official API (free), Y disambiguated via
legal pages (~Y credits), Z estimated, W not_found. Kill-rule matches
flagged: N rows under the size threshold." Max 3 sample rows.

## Notes for downstream bricks

- `executives` (with roles like Gérant / Président) is the direct food
  of `/bricks:enrich-buying-committee` — for small companies the
  decision-maker is already in this column, zero extra cost. Column
  relay, no call.
- `employees` + `country` are the cheapest kill-rule columns: run this
  skill early, `/bricks:score`'s kill gate gets its early-stop material
  for free.
