---
name: rank-accounts
description: Prioritize accounts — fuse ICP fit and every fresh signal into a priority_score /100, a priority_tier (now/week/nurture) and a why_now one-liner per company, so the agent tells you WHO to call first and WHY. Use when the user says "classe mes comptes", "qui appeler en premier", "priorise", "call list", "rank accounts", "priority score", "why now". Deterministic Python (one pass, zero model, zero credit); reads fit + signals, writes priority columns via db.py.
---

# Rank accounts

The prioritization brick — the call-list brain. `score` says how well a
company FITS the ICP (static); `find-hiring-signal` says whether one
hiring signal was worth committing. This brick answers the question
NEITHER does: *across all my accounts, which do I call NOW, and why?* It
fuses the fit (`tier`) with every fresh `signals` row into one
`priority_score` and a `why_now` line, then hands both to the bus —
`plan-outreach` reads the priority, `write-outreach` reads the `why_now`
as its opener. It NEVER calls another brick. Contract in this directory's
BRICK.md.

The maths live in a frozen script — `scripts/rank.py`, Mode A: one
deterministic for-loop, zero LLM, zero network, milliseconds on
thousands of rows. The model writes NO code; at most it edits one weight
in `scripts/rank_spec.json`. Same inputs + same spec = same ranking,
forever — a priority a jury can audit.

## Before anything

Follow `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` §2 and §3. This brick is
**free** and touches no external service — the FullEnrich gate (§4) does
not apply. It runs LATE (after find/enrich/score/signals): a ranking
without evidence is noise.

- **No `tier` column** (score never ran) → the ranking still runs on fit
  defaults, but SAY SO: "priorité basée sur les seuls signaux — lance
  score pour intégrer le fit ICP". Recommend score first.
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

## Run (deterministic, free — no pilot-wave ceremony)

1. Resolve the actual fit-tier column: `db.py schema companies` (§5,
   `--db <absolute path>`). It may be `tier`, `fit_tier`… — pass the real
   name as `--tier-col`.
2. Pull the inputs to files **by redirection** (they never ride the
   context, §10) — full tables, so `--limit -1`:

   ```bash
   RUN="<workspace>/staging/rank-<date>"; mkdir -p "$RUN"
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" select companies \
     --where "status IS NULL OR status!='disqualified'" \
     --cols _id,name,<tier-col> --limit -1 --db <db> > "$RUN/companies.json"
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" select signals \
     --cols company_id,company_name,kind,freshness,date,summary,evidence_url \
     --limit -1 --db <db> > "$RUN/signals.json"
   ```

3. Compute:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/rank-accounts/scripts/rank.py" run \
     --companies "$RUN/companies.json" --signals "$RUN/signals.json" \
     --spec "${CLAUDE_PLUGIN_ROOT}/skills/rank-accounts/scripts/rank_spec.json" \
     --tier-col <tier-col> --out "$RUN/updates.json"
   ```

   Deterministic + free → no `--preview`/GO ceremony (§10 applies to
   GENERATED content at volume; this is arithmetic). Announce it in one
   line and run.

## Commit — the database stays behind db.py

`rank.py` wrote `updates.json` as a ready `--updates` array. Commit in
ONE write (§5/§9.4, pass `--db`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/db.py" modify companies \
  --updates - --db <db> < "$RUN/updates.json"
```

This creates/fills `priority_score`, `priority_tier`, `why_now`,
`why_now_url` on `companies`. Also stamp `ranked_at=<date>` (bulk
`--set … --where "1=1"` excluding disqualified) so the front shows when
the ranking was last computed. No side "call-list" table — the list is
just `ORDER BY CAST(priority_score AS INTEGER) DESC` in the UI or a
`select`.

## Re-runnable by design

Signals decay, so priority is a SNAPSHOT: re-running recomputes every
live account from the current signals and freshness (no `pending/done`
per row — it is a full recompute, like plan-outreach re-proposing when
evidence shifts). Cheap and free, so re-run it after every signal pass.

## Close the run

`memory/state.json` (counts per band, `ranked_at`), one `NOTES.md` line.
Receipt: the band distribution (`now` / `week` / `nurture`), how many
carry a `why_now`, the run's `elapsed_s` (CONVENTIONS §8 — always relay
the wall-time), and the top 3 as `name → priority_score/tier →
why_now`. If `rank.py` reports `linkedByName > 0` or
`orphanedSignals > 0`, SAY SO — a signal writer omitted `company_id`
(the fallback recovered it by name, or dropped it): flag the brick to
fix upstream, don't let it pass silently. End with a **statement**, never a question — e.g. "Next:
write-outreach attaquera les comptes `now` en premier, `why_now` prêt en
accroche." The `why_now` is the handoff: write-outreach reads it as the
opener, plan-outreach reads `priority_tier` for per-priority treatment.
