# Brick contract: find-gmaps

| Field | Value |
|---|---|
| family | find |
| target | companies |
| method | deterministic `tools/gmaps.py` (Bright Data Google Maps dataset, `discover_new` by location, pure HTTP) → provisional CSV → `db.py import-csv` |
| cost | metered — Bright Data bills per record returned; `--limit` per query is the cap |

## IN

- A keyword + one or more locations (or ready-made Maps queries), country
  code (default FR), `--limit` records per query (default 50).
- Requires `BRIGHTDATA_API_TOKEN` in `~/.bricks/env` (envfile lane — no
  MCP involved).

## OUT

- `companies` rows: `name`, `domain` (dedup key), `phone`, `address`,
  `category`, `rating`, `reviews_count`, `query`, `source='gmaps'`,
  `status='new'`.
- Places without a usable company domain (no website, or a platform link
  — Facebook, Instagram, linktr.ee…) are DROPPED and counted in the
  receipt — a domain is never guessed.

## Errors

- Token absent → stop with the envfile setup note (§5).
- Snapshot not ready after 30 min → tool exits with the `snapshot_id`;
  resume later with `--snapshot <id>` — never resubmit (already paid).
- Import failure → the provisional CSV is KEPT and reported; deletion
  only follows a successful import.

## Guardrails

- Money gate (§8): plan announced as `queries × limit` records; above the
  big-spend threshold → ONE grouped GO. `snapshot_id` stored in
  `memory/state.json` the moment it exists — never pay twice.
- The full-CSV stdout dump is absorbed by the fork's disposable context
  (`context: fork`) — the session sees only receipts (§10).
- The tool never touches `bricks.db`; the single write path is
  `db.py import-csv --key domain` (§5), so re-runs dedup safely.
- The provisional CSV is deleted after commit — the database is the only
  checkpoint (§6).
