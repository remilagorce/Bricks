# Brick contract: playbook-lookalike

| Field | Value |
|---|---|
| family | playbook (composes skills — not a primitive) |
| target | companies (seeds + candidates), then downstream |
| method | orchestration: runtime discovery of installed skills, chained through the database |
| cost | sum of the composed skills — two human checkpoints gate the spend |

## IN

- Best customers from ANY source: CRM export/credential (detected by
  shape, honest fallback), CSV, or dictated list.
- Whatever enrichment skills are installed (discovered at runtime).

## OUT

- `companies`: seeds tagged `segment='seed'`, enriched; candidates
  sourced and filtered on the discriminating signal.
- `memory/state.json` + `NOTES.md`: phase progress, pattern, signal.

## Hard rules

- Checkpoint 1: pattern + discriminating signal confirmed by the user
  (end of Phase 3). Checkpoint 2: money gate before any paid enrichment
  of candidates (Phase 5).
- No hardcoded skill list — degrade gracefully with what is installed.
- Never fake a CRM connection.
- Resumable at every phase (statuses + state.json).
