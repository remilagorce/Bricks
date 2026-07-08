# Bricks — the skill contract

Every skill under `plugins/bricks/skills/` reads THIS file before acting. It is
the shared runtime contract: the rules below are assumed by every skill and
never repeated in full inside a `SKILL.md`. (How to *build and maintain* the
repo is a different audience — that lives in the root `CLAUDE.md`.)

Keep it short. If a rule stops fitting in a few lines, it belongs in a tool or a
skill, not here.

## §1 — Two planes

The conversation DECIDES; files and the database CARRY. The session never holds
row-level mass: bulk data lives in `bricks.db` or in a CSV on disk, never pasted
into the chat. Receipts, not dumps — max 3 sample rows in a reply. The test:
does the model need to *read* this to decide? No → it goes through a file, not
the context.

## §2 — Workspace resolution

The Bricks root (`bricks/` in the working directory) is created LAZILY, on the
first GTM action — nothing is created just by opening a session. Begin any GTM
action with:

    python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/workspace.py" status

- Not initialized here, or no **current workspace** → create one (`new <slug>`,
  which also creates the root) or `switch` to an existing one. If the user's
  request implies a name (client, campaign, project), create it without asking
  first. After `new`/`switch`, display the returned banner.
- Never edit `config.json` or any workspace file by hand — go through
  `workspace.py`.

## §3 — Context gate

A workspace carries a `context/` (offer, ICP, personas). Before sourcing or
enriching, read `context/offer.md` and `context/icp.md`. Talk about their
*content*, never their filenames. If the request contradicts the context
(different product, different ICP, different target), STOP and ask: switch, new
workspace, or update the context. If the ICP is still empty (TODO placeholders),
hand off to `/bricks:gtm-onboard` before sourcing. If the ICP has kill rules
matching columns being written, flag matching rows in the receipt — never
disqualify silently.

## §4 — The only door: db.py

Every read and write to workspace data goes through `db.py` — never raw SQL,
never the `sqlite3` CLI, never mass data inlined in the conversation. Tables
and columns are dynamic; `_id` is auto-generated (never pass it in). An
enrichment column `X` is paired with `X_status` using the shared vocabulary:
`pending | running | done | not_found | failed`. `not_found` is a result, not
an error; `failed` means retryable; NEVER fabricate a value. Full CLI and
function signatures in `/bricks:tools-guide`.

## §5 — The iron gate: preview → GO → commit

Every mass write runs `runner.py run … --preview 10` first: the 10 rows are
computed, WRITTEN (tagged with the run-id) and streamed live — tell the user to
check them in the interface. The user gives ONE explicit GO; only then the same
command with `--commit` (preview rows are settled, never re-paid). Statuses are
the checkpoint: re-running resumes the pending rows; `release` frees rows a
crash left `running`; `--retry-failed` is the explicit retry pass. Every row
written carries the run-id — `runner.py rollback --manifest <run>.manifest.json`
erases a bad run entirely (fields nulled, statuses reset, child rows removed).

## §6 — One path in, one path out

- **Sourcing** (any external fetch producing many rows) → land a CSV on disk
  (`staging/` in the workspace for raw or interruptible batches), then
  `db.py import-csv <table> <file> --key <col>`. Never mass `--rows` JSON
  typed in the conversation (a script piping its output to `--rows -` via
  stdin is fine — the mass stays out of the context), and never page bulk
  provider data through MCP replies — export CSV instead.
- **Enrichment** → either (A) pass-through data the user already has, written
  as-is (`import-csv`, or a small `modify`), or (B) computed per row through
  `runner.py` (steps and/or `--ai` → `agent.py`). One mode per run — never a
  third path: no per-row loops in the conversation, no hand-calling `agent.py`
  row by row (≲5 rows dictated in-session is the exception — see
  `/bricks:brickgent`).

## §7 — References, cost & billing

- Reference other skills as slash commands, never as file paths:
  `/bricks:find`, `/bricks:enrich`, `/bricks:score`, `/bricks:tools-guide`… —
  pattern `/bricks:<skill-directory-name>`.
- Per-row work defaults to `haiku` — the strong model is for orchestration,
  not for 500 identical worker turns. Announce a batch's scope and worst-case
  cost (rows × pages × credits) BEFORE committing it. Below the big-spend
  threshold (default **50 credits**, adjustable by the user's word) →
  announce and RUN; above → ONE explicit GO.
- The engine runs on the Claude **subscription** by default (Agent SDK).
  `BRICKS_AGENT_TRANSPORT=api` switches to the Anthropic API (API credits) —
  needed where the SDK cannot run. Caution: an `ANTHROPIC_API_KEY` present in
  the environment (`~/.bricks/env`) takes precedence over the subscription
  login even on the SDK path.

## §8 — Workspace memory

Cross-run state lives in the workspace, not the conversation:
`memory/state.json` (cursors, quotas, async job ids — an interrupted run picks
up instead of paying twice) and `memory/NOTES.md` (one summary line per run).
