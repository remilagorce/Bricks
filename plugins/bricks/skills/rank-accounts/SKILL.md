---
name: rank-accounts
description: Prioritize accounts — fuse ICP fit and every fresh signal into a priority_score /100, a priority_tier (now/week/nurture) and a why_now one-liner per company, so the agent tells you WHO to call first and WHY. Use when the user says "classe mes comptes", "qui appeler en premier", "priorise", "call list", "rank accounts", "priority score", "why now". Deterministic Python (one pass, zero model, zero credit); reads fit + signals, writes priority columns via db.py.
---

# Rank accounts

**Before anything, read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`.**

The prioritization brick — the call-list brain. `/bricks:score` says how
well a company FITS the ICP (static); the signal bricks say what is
happening NOW. This brick answers the question NEITHER does: *across all
my accounts, which do I call NOW, and why?* It fuses the fit (`tier`)
with every fresh `signals` row into one `priority_score` and a `why_now`
line, then hands both to the bus — `/bricks:plan-outreach` reads the
priority, `/bricks:write-outreach` reads the `why_now` as its opener. It
NEVER calls another brick.

The maths live in a frozen script — `scripts/rank.py`: one deterministic
for-loop, zero LLM, zero network, milliseconds on thousands of rows. The
model writes NO code; at most it edits one weight in
`scripts/rank_spec.json`. Same inputs + same spec = same ranking, forever
— a priority a jury can audit.

## Before anything

This brick is **free** and touches no external service. It runs LATE
(after find/enrich/score/signals): a ranking without evidence is noise.

- **No `tier` column** (score never ran) → the ranking still runs on fit
  defaults, but SAY SO: "priorité basée sur les seuls signaux — lance
  `/bricks:score` pour intégrer le fit ICP".
- **No `signals` table / no rows** → every account scores on fit alone
  and lands in `week`/`nurture` with an empty `why_now` — that is the
  correct, honest result for a no-signal base (the control-group case),
  not an error.

## The logic (what the script does — read `rank.py`'s docstring for the spec)

Per company, in one pass: aggregate its signals → take the STRONGEST
fresh one → `priority_score = fit(tier) + kind_points × freshness +
volume_bonus`, capped and distress-capped → `priority_tier`
(`now` ≥ 70 · `week` ≥ 40 · `nurture`) → `why_now` = a template line from
the strongest signal + its `why_now_url`. Freshness is read from each
signal's real `date` when present (≤7d full weight, decaying to
`context`), else from its `freshness` label. Weights and thresholds are
the "holes" in `scripts/rank_spec.json` — the user tunes them by saying
so ("mets hiring à 40", "seuil now à 75") and you edit that one value.

## Run (deterministic, free — no preview/GO ceremony)

1. Resolve the actual fit-tier column: `db.py schema companies` (§4). It
   may be `tier`, `fit_tier`… — pass the real name as `--tier-col`.
2. Pull the inputs to files **by redirection** (they never ride the
   context, §1) — full tables, so `--limit -1`:

   ```bash
   RUN="bricks/tmp/rank-<date>"; mkdir -p "$RUN"
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" select companies \
     --where "status IS NULL OR status!='disqualified'" \
     --cols _id,name,<tier-col> --limit -1 > "$RUN/companies.json"
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" select signals \
     --cols company_id,company_name,kind,freshness,date,summary,evidence_url \
     --limit -1 > "$RUN/signals.json"
   ```

3. Compute:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/rank-accounts/scripts/rank.py" run \
     --companies "$RUN/companies.json" --signals "$RUN/signals.json" \
     --spec "${CLAUDE_PLUGIN_ROOT}/skills/rank-accounts/scripts/rank_spec.json" \
     --tier-col <tier-col> --out "$RUN/updates.json"
   ```

   Deterministic + free → the iron gate (§5) applies to GENERATED content
   at volume; this is arithmetic. Announce it in one line and run.

## Commit — the database stays behind db.py

`rank.py` wrote `updates.json` as a ready `--updates` array. Commit in
ONE write (§4):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" modify companies \
  --updates - < "$RUN/updates.json"
```

This creates/fills `priority_score`, `priority_tier`, `why_now`,
`why_now_url` (and `ranked_at`, stamped by rank.py in each update row) on
`companies`. No side "call-list" table — the list is just `ORDER BY
CAST(priority_score AS INTEGER) DESC` in the UI or a `select`.

## Re-runnable by design

Signals decay, so priority is a SNAPSHOT: re-running recomputes every
live account from the current signals and freshness (no `pending/done`
per row — it is a full recompute). Cheap and free, so re-run it after
every signal pass.

## Receipt

The band distribution (`now` / `week` / `nurture`), how many carry a
`why_now`, the run's `elapsed_s`, and the top 3 as `name →
priority_score/tier → why_now`. If `rank.py` reports `linkedByName > 0`
or `orphanedSignals > 0`, SAY SO — a signal writer omitted `company_id`
(the fallback recovered it by name, or dropped it): flag the brick to fix
upstream, don't let it pass silently. End with a **statement**, never a
question — e.g. "Next: `/bricks:write-outreach` attaquera les comptes
`now` en premier, `why_now` prêt en accroche."
