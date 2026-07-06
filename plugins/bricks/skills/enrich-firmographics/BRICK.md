# Brick contract: enrich-firmographics

| Field | Value |
|---|---|
| family | enrich (company level) |
| target | companies |
| method | script (`tools/firmo.py` → official French government API) + Bright Data for disambiguation/estimates; writes via `db.py` |
| cost | free (pass 1, unlimited) · ~1 Bright Data credit per ambiguous/foreign row (passes 2-3) |

## IN

- `companies.name` (required), `firmo_status='pending'`,
  `status != 'disqualified'`.
- Optional locality hints sharpen matching: `city`, `postal`, `domain`.
- Optional: `mcp__brightdata__*` for passes 2-3 (without it those rows
  stay pending).

## OUT

- `employees` (range string, e.g. "50-99"), `industry` (NAF section
  label), `naf` (code), `siren`, `city`, `executives` (JSON list of
  {name, role}, statutory auditors excluded; `entity: true` marks
  corporate officers).
- `parent_company` when the legal representative is a company — the
  "group-owned, not independent" signal, receipt-flagged for kill rules.
- `company_category` (INSEE: PME | ETI | GE, computed at GROUP level) —
  GE/ETI with a small local headcount = subsidiary signal, even when the
  registry lists no corporate officer.
- `firmo_status` → `done` | `not_found` | `failed`;
  `firmo_source='estimate'` marks pass-3 grade data.
- Rows already carrying a `siren` are re-looked-up exactly (no matching
  ambiguity) — pass-2 outputs re-enter pass 1 cleanly.

## Errors

- API unreachable → `failed` (retryable), never switch to guessing.
- Ambiguous with no SIREN on the legal page → `not_found`.
- Estimates never cover `siren`/`executives` — official identifiers are
  real or absent.

## Guardrails

- Pass 1 is one batched script call — fast, free, unblockable (official
  public API, self rate-limited under 7 req/s). Bright Data is surgical
  (money gate §8 applies at volume).
- Kill-rule matches (size/country) are FLAGGED in the receipt, never
  silently disqualified — that is the score skill's job.
- Idempotent re-runs via `firmo_status`; subagent findings go through
  staging, `db.py` commits.
