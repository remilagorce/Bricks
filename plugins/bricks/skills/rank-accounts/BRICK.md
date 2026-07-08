# Brick contract: rank-accounts

| Field | Value |
|---|---|
| family | rank (prioritization — reads fit + signals, writes priority columns) |
| target | reads companies (`tier`) + signals; writes companies.priority_score / priority_tier / why_now / why_now_url / ranked_at |
| method | deterministic Python one-pass (`scripts/rank.py`): aggregate signals → fuse fit × strongest-fresh-signal × freshness + volume → score /100 + band + why_now template. Weights in `scripts/rank_spec.json` (the holes). |
| cost | free (zero model, zero network, zero credit) |

## IN

- `companies` rows where `status` is not `disqualified`, with a fit tier
  column (`tier` / `fit_tier` — resolved via `db.py schema`, passed as
  `--tier-col`). No tier → fit defaults, flagged (run score first).
- `signals` rows (from signal-person / find-hiring-signal /
  signal-sillage): `company_id`, `kind`, `freshness`, `date`, `summary`,
  `evidence_url`. No signals → fit-only ranking, empty why_now (the
  honest no-signal result, not an error).
- Inputs pulled to `staging/rank-<date>/*.json` by redirection — never
  ride the context (§10).

## OUT

- `companies.priority_score` (0-100), `priority_tier`
  (`now` ≥ 70 · `week` ≥ 40 · `nurture`), `why_now` (one-line trigger
  from the strongest signal), `why_now_url` (its evidence), `ranked_at`.
  Written in ONE `db.py modify --updates -` from `rank.py`'s
  `updates.json` (§9.4).
- No new table: the call-list is `ORDER BY priority_score DESC`.
- `memory/state.json` (band counts, ranked_at) + NOTES.md line.

## Errors

- No `tier` column → runs on fit defaults, flagged ("run score first").
- No `signals` / empty → fit-only ranking, empty why_now (correct).
- Disqualified companies excluded at the select (never ranked, §8.5).
- Distress signal (`warning`) → score capped low even for a fit-A row.

## Guardrails

- Runs AFTER score + signals — fit and evidence first, never vibes.
- The maths are FROZEN in `rank.py`; the model never generates scoring
  code — it edits at most one value in `rank_spec.json`. Same inputs +
  same spec = same ranking (jury-explainable).
- Re-runnable snapshot: recomputes all live accounts each run (signals
  decay); freshness re-read from `date` at run time.
- Never calls another brick — `priority_tier` and `why_now` are
  artifacts on the bus (plan-outreach reads the tier, write-outreach
  reads the why_now). Never writes messages, never sends.
- Receipts are statements, never questions.
