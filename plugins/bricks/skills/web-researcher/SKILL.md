---
name: web-researcher
description: Enrich table rows from ANY natural-language question — "est-ce qu'ils ont une casquette bleue ?", "trouve le téléphone du standard", "quelle est leur forme juridique ?" — via the engine, one disposable agent per row (web-connected or not), structured multi-column output, preview of 10 before the mass. Use when the user asks a per-row question no specialized brick covers, or says "web research", "recherche pour chaque ligne", "pose cette question à chaque entreprise", "enrichis à partir de cette question".
---

# Web researcher

The Swiss-army enrichment brick: turns ANY question about each row into
filled columns, at any volume, without a single row or page ever
transiting the conversation. The session compiles; the engine executes
(CONVENTIONS §11). Specialized bricks (enrich-firmographics,
enrich-buying-committee…) stay preferred when they cover the need —
this brick is for everything they don't.

## Before anything

Follow `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` §2 (workspace) and §3
(context gate — the question usually stands alone, but a kill rule that
maps to the asked column is worth flagging). FullEnrich is not needed.
`--tools web` needs the Bright Data token (`BRIGHTDATA_API_TOKEN` — the
same one the session's MCP uses; the engine self-loads it from
`~/.bricks/env`, §11); absent → run `--tools none` lanes only and say
so. Workers need `CLAUDE_CODE_OAUTH_TOKEN` in the same file (desktop
sandboxes cannot read the Keychain login).

**Scale rule (§10)**: ≲5 rows, or a one-off question dictated in the
conversation → handle it IN-SESSION (the session has the MCP at hand),
write via `db.py` if the user wants it stored; no engine, no ceremony.
Volume → the engine, below.

## 1. Compile — the only judgment in the run

Turn the user's question into the two prompt files, in the workspace:

```
<workspace>/prompts/<slug>/instructions.md   # the mission, {{column}} variables
<workspace>/prompts/<slug>/schema.json       # output fields → columns
```

- `instructions.md`: the question, precise, with `{{column}}` variables
  where row values belong (e.g. « Trouve le téléphone du standard de
  {{name}}, site {{domain}} » ). State what counts as a valid answer
  and where to look first. The engine appends the row's data block and
  the anti-invention rules itself — do not restate them.
- `schema.json`: one field per output column, with a one-line
  description each: `{"fields": {"telephone": "numéro du standard,
  format international"}, "evidence": true}`. Multi-field = multi-column
  (Clay-style structured output).
- Show the user the compiled prompt in 3-5 lines and confirm ONCE —
  their question, their columns. Re-runs reuse the files silently.

## 2. Announce, preview, GO, commit (§8 + §10)

1. Init the status column on rows in scope (`db.py modify --set
   <slug>_status=pending`, §5), skip disqualified.
2. **Announce the budget**: N rows × `--max-pages` worst case when
   `--tools web` (Bright Data credits), model choice (default `haiku` —
   raise only if the judgment demands it), expected duration (an agent
   that navigates ≈ 30-60 s; 8 workers ≈ 10-15 rows/min — a 10 000-row
   web run is an overnight run, say so plainly). Below the big-spend
   threshold → announce and RUN; above → ONE GO.
3. **Preview**: `runner.py run … --preview 10` (contract in §11). The
   10 rows land in the database, tagged — tell the user to check them
   in the interface, show ≤3 samples in the receipt, and STOP for the
   GO. A bad prompt costs 10 rows, never 5 000.
4. **Commit**: same command with `--commit` — tranches, parallel
   workers, wave writes, resumable at any interruption (`release` for
   crashed rows, `--retry-failed` for an explicit retry pass).

## 3. Close the run

Receipt: reconciled counts ("512 claimed = 480 done + 22 not_found +
10 failed (top reasons)"), spend vs announced, manifest path, and the
rollback line ("`runner.py rollback --manifest …` annule tout ce run").
Max 3 sample rows. Statements, never questions. The columns are now
ordinary enrichment columns — score, plan-outreach and write-outreach
read them like any other.
