---
name: score
description: Score table rows from natural-language rules — arithmetic on columns, conditional points ("si CTO score 4"), and judged measures with a rubric ("évalue l'innovation tech 1-10"). Use when the user says "score", "note mes lignes", "kill gate", "applique mes règles de scoring", "tier A/B/C". File-based and deterministic — compiles rules into a spec, materializes judgments once, computes with a pure script; never writes the database directly.
---

# Score

**Before anything, read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`.**

Turns natural-language scoring rules into an auditable, replayable score
per row. The architecture separates judgment from calculation: the model
compiles rules ONCE into a spec, judges (via `agent.py`, the single AI
door) materialize the fuzzy measures ONCE as columns, and a pure Python
kernel computes everything — same file + same spec = same scores, forever,
explainable to a jury. One intermediate `sc_*` column per rule so the
decomposition is visible.

This skill is file-based by design: it NEVER touches `bricks.db`.
Committing scores back to a workspace table is a separate, atomic step
via `db.py` after the run (see Handoff). The run directory lives in
`bricks/tmp/score-<YYYY-MM-DD>/`. If no workspace exists and the user is
scoring an ad-hoc file, a temp directory is acceptable; say so in the
receipt. Read `context/icp.md` when the rules reference the ICP (kill
rules, fit criteria) — context gate §3 applies.

## 1. Intake — everything becomes one canonical file

Accept either input, normalize to `<rundir>/work.jsonl` (one JSON object
per line):

- **A table described in text / pasted** → parse it and write the JSONL
  yourself.
- **A file path** (CSV or JSONL) → convert CSV to JSONL; copy into the
  run dir.
- **Workspace rows** → `db.py select <table> --limit -1` (§4), save its
  JSON output as the JSONL. Keep `_id` in the rows: the handoff needs it
  to modify by id.

Do not invent columns; the file is scored as-is.

## 2. Compile — the rules become a spec (the ONLY main-thread judgment)

Translate the user's natural-language rules into `<rundir>/spec.json`.
The full spec format (rule kinds, condition operators, tiers) is
documented at the top of `scripts/score.py` — read it before writing the
spec. The three kinds map to what users say:

- "additionne/soustrais colonne A et B" → `arithmetic`
- "si CTO score 4, si CEO score 6, si <40 employés score 5" →
  `conditional` (one `into` column per theme, e.g. `sc_role`, `sc_size`;
  first matching rule wins inside one `into`)
- "lis la description et évalue X de 1 à 10" → `measure` with a `rubric`
- "exclure les non-français" → `kill` (flags `killed` + `kill_reason`;
  never deletes, never spends downstream)
- "tier A/B/C à partir du score" → optional `tiers` block in the spec
  (thresholds → column `tier`)

Rules for writing measures — this is where scoring quality is decided:

- **Judge on real signal, never on a label.** A `measure`'s `rubric.input`
  must point at a column carrying genuine per-row content (a description, a
  scraped page, a rich free-text field). If the only inputs available are
  coarse labels (`industry`, `segment`, a sector tag) — especially ones a
  deterministic rule already uses — the judge has nothing to read: it just
  echoes the label back, producing confident-but-hollow scores that don't
  discriminate (field-tested: a "travel intensity" measure fed only the
  sector tag scored a data/BI firm 10 and a near-identical one 5). Two ways
  out, both better than a hollow judge: (a) if the label is enough, make it
  a deterministic `conditional` on that column — no judge, no cost, fully
  explainable; (b) if it truly needs judgment, ENRICH the descriptive
  column first via `/bricks:enrich` (it's free to re-score once the data
  lands), then judge on it. When neither is possible, say so in the receipt
  and mark the axis as a low-confidence inference rather than presenting it
  as a measured score.
- **Force intermediate anchors.** If the user only gave the extremes
  ("10 = deep tech, 1 = innovation produit"), propose 2 intermediate
  anchors and get a quick confirmation — anchors are what make two
  batches judged separately comparable.
- **Gates are deterministic when possible.** "si c'est une entreprise
  tech" → a `gate` condition on an existing column (`industry`). Rows
  failing the gate get 0 and are never sent to a judge. Only fold the
  gate into the rubric when no column can answer it.
- **Evidence on by default.** Each judged value comes with a verbatim
  quote (`<label>_evidence` column) — a judgment without inspectable
  evidence does not exist.

Show the user the spec summary (one line per rule: label, kind, points)
before running. Their rules, their weights — confirm anything you had to
interpret.

## 3. Check, announce, run

```bash
cd <rundir>
python3 "${CLAUDE_PLUGIN_ROOT}/skills/score/scripts/score.py" check work.jsonl spec.json
```

`hardMissingColumns` non-empty → STOP: the spec references columns the
file does not have. Fix the spec or the intake — never guess data.

Then dry-run to size the judgment work, and announce it before running
(N judge calls ≈ N agent invocations on the user's subscription — same
spirit as the iron gate, announce volume first; skip the announcement
when `judgeCalls` is 0):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/score/scripts/materialize.py" run work.jsonl spec.json --dry-run
python3 "${CLAUDE_PLUGIN_ROOT}/skills/score/scripts/materialize.py" run work.jsonl spec.json --workers 4
```

`materialize.py` does everything from there, streaming — do NOT judge
rows yourself in the conversation, and do not wait to post-process
between stages:

- rows needing no judgment are scored and appended to `scored.jsonl`
  immediately;
- measure gaps are judged in parallel batches through `agent.py`
  (schema-guaranteed answers, rubric passed verbatim); each answer is
  validated (bounds, evidence) and checkpointed to `judgments.jsonl` — an
  interrupted run resumes without re-judging (never pay twice);
- each row is scored the moment its LAST judgment lands.

Re-scoring after a weight change is free: edit `spec.json`, re-run —
materialized judgments are reused from the columns/checkpoint.

## 4. Receipt — receipts, not dumps

Report: rows scored, score min/max and tier distribution, killed count
(with top reasons), `missingInput`/`failedRows` if any (name the rows,
offer a retry — failed batches are NOT checkpointed so a re-run retries
exactly them). Show at most 3 sample rows as `input → sc_* decomposition
→ score/tier`, including `<label>_evidence` for judged measures so the
user can contest the judgment, not just the total.

## 5. Handoff — the database stays outside

If the rows came from the workspace, propose committing the scores:
one `db.py modify <table> --updates -` (§4) fed from `scored.jsonl`
(`_id` + score/tier/`sc_*` columns), and translate `killed='true'` into
`status='disqualified'` in those same update objects (downstream bricks
filter them out and never spend on them again).

**Do not bother with row order at commit time.** `scored.jsonl` may be
in streaming completion order — that is fine. Write each row by `_id`;
no pre-sort, no reorder pass, no special tier batching. Sorting and
filtering by score or tier happen in the database or the UI whenever
the user wants them.

Close the run: `memory/state.json` (rundir, counts) + one `NOTES.md`
line ("scored N rows: rules X/Y/Z, K killed") — §8.

End the receipt with a **statement of the next step, never a question** —
"Next: `/bricks:rank-accounts` fusionnera ce fit avec les signaux frais —
dis le mot." One announced direction, the user redirects if they disagree.
