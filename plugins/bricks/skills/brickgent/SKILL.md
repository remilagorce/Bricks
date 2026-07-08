---
name: brickgent
description: Agent that performs AI enrichment directly on table rows — e.g. browse a company's website looking for news, a contact email address, or relevant facts to write the icebreaker. One disposable agent per row (web-connected or not), structured multi-column output, preview of 10 before any mass write. Also handles one or a few rows given directly in the conversation by dispatching pre-built prompts to isolated agents. Use when the user asks a per-row AI question no specialized brick covers, or says "brickgent", "web research", "recherche pour chaque ligne", "pose cette question à chaque entreprise", "enrichis à partir de cette question", "traite ces lignes avec l'IA".
---

# brickgent

Any question about rows becomes filled columns (or direct answers), without
a single scraped page ever transiting the conversation. The session compiles
a PRECISE prompt; a disposable agent executes it. Specialized bricks
(`/bricks:enrich-firmographics`, `/bricks:enrich-buying-committee`…) stay
preferred when they cover the need — brickgent is for everything they don't.

Read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` — §2 (workspace), §3 (context
gate), §5 (iron gate), §7 (cost & billing). FullEnrich is not needed. The
web lane needs `BRIGHTDATA_API_TOKEN` (same token as the session's MCP;
self-loaded from `~/.bricks/env`); absent → run non-web lanes only and say so.

**Prompt discipline** — ALWAYS generate a precise, structured prompt:

```
###Context###
You are a web research agent whose job is to find the right
information by browsing the company's website.
###Instruction###
<the precise mission — what to find, what counts as a valid answer,
where to look first>
```

A gallery of ready-to-adapt prompts per use case (site news, contact email,
icebreaker facts) lives in `exemple.md` — read it before writing the first
prompt.

## Two regimes — where does the data live?

### Rows IN the database (several) → the engine loop

The prompt uses `{{nom_colonne}}` brackets — the EXACT column names,
replaced with each row's values at run time.

1. **Look at the table**: `db.py schema <table>` + `db.py select <table>
   --limit 3` (§4) — the real column names come from here.
2. **Compile** — the `###Context###/###Instruction###` prompt with
   `{{col}}` brackets, plus the output schema (one property = one column,
   with a one-line description each). Long mission → write it as
   `prompts/<slug>/params.json` in the workspace and pass `--ai @<path>`
   (re-runs reuse the file silently). Show the user the compiled prompt in
   3-5 lines and confirm ONCE.
3. **Init the lane** (first run only): `db.py modify <table> --set
   <slug>_status=pending --where "…"` on rows in scope — disqualified rows
   are never claimed.
4. **Announce the budget** (§7): N rows × `max_pages` worst case when
   `"web":true`, model (default `haiku` — raise only if the judgment
   demands it), expected duration (a browsing agent ≈ 30-60 s/row; 12
   workers ≈ 15-20 rows/min — a 10 000-row web run is an overnight run,
   say so plainly). Below the big-spend threshold → announce and RUN;
   above → ONE GO.
5. **Preview (the iron gate §5)**:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/runner.py" run --table <table> \
  --status-col <slug>_status --run-id <slug>-<YYYY-MM-DD> \
  --ai '{"prompt":"###Context### … ###Instruction### … {{name}} {{domain}} …",
         "schema":{"type":"object","properties":{"…":{"type":"string","description":"…"}}},
         "web":true,"model":"haiku"}' \
  --preview 10
```

   The 10 pilot rows are computed, WRITTEN tagged with the run-id, and
   streamed on stderr as NDJSON (`preview_start`, then one `preview_row`
   per finished row) — **relay each line to the user as it arrives** and
   tell them to check the rows in the interface. Then STOP for the GO.
   A bad prompt costs 10 rows, never 5 000.
6. **Commit** — same command with `--preview 10` → `--commit`: tranches,
   parallel workers, wave writes, resumable at any interruption (`release`
   for crashed rows, `--retry-failed` for an explicit retry pass). Preview
   rows are settled — never re-paid.

### One or a few rows given directly (≲5, no engine, no ceremony)

Info dictated in the conversation, or already at hand → build the prompt(s)
ON THE FLY with the REAL values (NO brackets) — one prompt per row, same
`###Context###/###Instruction###` template — and dispatch each one to a
**detached subagent** (the Agent tool, general-purpose): its prompt is the
pre-built prompt, plus — when the answer is on the web — the instruction to
browse with the session's Bright Data MCP tools (`mcp__…brightdata__*`) and
to return ONLY the answer. Fire one subagent per row, IN PARALLEL when
several. The scraped pages stay in the subagent's disposable context (§1).

Variant — when a SCRIPT needs the call, or the answer must be
schema-guaranteed JSON, or the Bright Data MCP is not connected (the CLI
uses `BRIGHTDATA_API_TOKEN` instead):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/agent.py" \
  --prompt '###Context### … ###Instruction### …' \
  [--web] [--model haiku] [--schema '{…}']
```

Relay the answers; if the user wants them stored, `db.py` writes per §4.
Beyond a handful of rows → import into the base and take the engine lane.

## Close the run

Receipt: reconciled counts («512 claimed = 480 done + 22 not_found + 10
failed (top reasons)»), spend vs announced, and the two resume lines —
«re-lancer la même commande reprend les pending» and «`runner.py rollback
--manifest <run>.manifest.json` annule tout ce run». Max 3 sample rows.
Statements, never questions. The columns are now ordinary enrichment
columns — `/bricks:score`, `/bricks:plan-outreach` and
`/bricks:write-outreach` read them like any other.
