---
name: brickgent
family: source
description: Agent that performs AI enrichment directly on table rows — e.g. browse a company's website looking for news, a contact email address, or relevant facts to write the icebreaker. One disposable agent per row (web-connected or not), structured multi-column output, dry-run of 10 before any mass write. Also handles one or a few rows given directly in the conversation by dispatching pre-built prompts to isolated agents. Use when the user asks a per-row AI question no specialized brick covers, or says "brickgent", "web research", "recherche pour chaque ligne", "pose cette question à chaque entreprise", "enrichis à partir de cette question", "traite ces lignes avec l'IA".
---

# brickgent

Any question about rows becomes filled columns (or direct answers),
without a single scraped page ever transiting the conversation. The
session compiles a PRECISE prompt; a disposable agent executes it.
Specialized bricks (enrich-firmographics, enrich-buying-committee…) stay
preferred when they cover the need — brickgent is for everything they
don't.

**Cost & auth doctrine** — brickgent is the engine's AI lane. Inside a Claude
Code session, workers **inherit the same subscription and MCP** as the session
(plugin ``.mcp.json`` + user settings; Keychain auth is propagated to the
SDK subprocess). ``~/.bricks/env`` is only needed for standalone runs outside
a session, or for ``BRIGHTDATA_API_TOKEN`` when Bright Data isn't connected via
``/mcp``. API billing only if ``ANTHROPIC_API_KEY`` is deliberately set.

**Prompt discipline** — ALWAYS generate a precise, structured prompt:

```
###Context###
You are a web research agent whose job is to find the right
information by browsing the company's website.
###Instruction###
<the precise mission — what to find, what counts as a valid answer,
where to look first>
```

A gallery of ready-to-adapt prompts per use case (site news, contact
email, icebreaker facts) lives in `exemple.md` — read it before writing
the first prompt.

## Before anything

Follow `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` §2 (workspace) and §3
(context gate). FullEnrich is not needed.

## Two regimes — where does the data live?

**Rows IN the database (several)** → the engine loop, prompt WITH
brackets. The `{{nom_colonne}}` brackets use the EXACT column names of
the table and are replaced with each row's values at run time. The
order:

1. **Look at the table**: `db.py schema <table>` + `db.py select
   <table> --limit 3` (§5) — the real column names come from here.
2. **Generate the prompt** from the user's request — the
   `###Context### / ###Instruction###` template above, with
   `{{nom_colonne}}` brackets where row values belong — plus the output
   schema (one field = one column, inline JSON). Show both in 3-5
   lines, confirm ONCE.
3. **Init the status column** on rows in scope (`db.py modify --set
   <slug>_status=pending`, §5), then **dry-run** — computes the first
   10 rows, streams each result as it finishes, writes NOTHING (Rule 5).
   While the command runs, **read stderr line by line** and relay each
   `preview_row` to the user so they see progress — do not wait for the
   final stdout JSON:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/runner.py" --table <table> \
  --ai '{"prompt":"###Context### … ###Instruction### … {{name}} {{domain}} …",
         "schema":{"type":"object","properties":{"…":{"type":"string"}}},
         "web":true,"model":"sonnet"}' \
  --status-col <slug>_status --limit 10
```

Stderr NDJSON events: `preview_start` (count), then one `preview_row`
per finished row (`_id` + `fields` or `error`). Stdout = final receipt
only after all rows complete.

4. **Confirmation (GO)** → same command with `--commit` — the whole
   table, tranches, wave writes, resumable; the manifest embeds the
   prompt and schema (traceability), `rollback` undoes the run. The
   commit recomputes the 10 pilot rows — accepted cost, announce it
   with the budget (§8: N rows × model × pages worst case; observed
   dry-run cost extrapolated).

**One or a few rows given directly** (in natural language in the
conversation, or info already at hand — no need to fetch from the
base) → no engine, no ceremony: build the prompt(s) ON THE FLY with the
REAL values (NO brackets) — one prompt per row, same
`###Context###/###Instruction###` template — and dispatch each one to
a **detached subagent** (the Agent tool, general-purpose): its prompt
is the pre-built prompt, plus — when the answer is on the web — the
instruction to browse with the session's Bright Data MCP tools
(`mcp__…brightdata__*`) and to return ONLY the answer. Fire one
subagent per row, IN PARALLEL when several. This runs on the session
side — no API key, no engine cost — and the scraped pages stay in the
subagent's disposable context (§9.5/§10), never in the session's.

Variant — when a SCRIPT needs the call, when the answer must be
schema-guaranteed JSON, or when the Bright Data MCP is not connected
(the CLI uses `BRIGHTDATA_API_TOKEN` instead):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/agents/researcher.py" \
  --prompt '###Context### … ###Instruction### …' \
  [--tools web] [--model haiku] [--structured '{…}']
```

Relay the answers; if the user wants them stored, `db.py` writes per
§5. Cap: a handful of rows (~5-10) — beyond that, import into the base
and go through the engine (brackets + dry-run + commit).

## Close the run

Receipt: reconciled counts ("512 claimed = 480 done + 22 not_found +
10 failed (top reasons)"), spend vs announced, manifest path, and the
rollback line ("`runner.py rollback --manifest …` annule tout ce run").
Max 3 sample rows. Statements, never questions. The columns are now
ordinary enrichment columns — score, plan-outreach and write-outreach
read them like any other.
