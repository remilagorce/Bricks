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
into the chat. The test: does the model need to *read* this to decide? No → it
goes through a file, not the context.

## §2 — Workspace resolution

The Bricks root (`bricks/` in the working directory) is auto-initialized by the
SessionStart hook, so `bricks/config.json` always exists — you NEVER run `init`.
Begin any GTM action with:

    python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/workspace.py" status

- No **current workspace** → create one (`new <slug>`) or `switch` to one. If
  the user's request implies a name (client, campaign, project), create it
  without asking first.
- Never edit `config.json` or any workspace file by hand — go through
  `workspace.py`.

## §3 — Context gate

A workspace carries a `context/` (offer, ICP, personas). Before sourcing or
enriching, read `context/offer.md` and `context/icp.md`. Talk about their
*content*, never their filenames. If the request contradicts the context
(different product, different ICP, different target), STOP and ask: switch, new
workspace, or update the context. If the ICP is still empty (TODO placeholders),
hand off to `/bricks:gtm-onboard` before sourcing.

## §4 — The only door: db.py

Every read and write to workspace data goes through `db.py` — never raw SQL,
never the `sqlite3` CLI, never mass data inlined in the conversation. Tables and
columns are dynamic; `_id` is auto-generated (never pass it in). Full CLI in
`/bricks:tools-guide`.

## §5 — The iron gate: preview → GO → commit

Every mass write runs `runner.py` WITHOUT `--commit` first (the first 10 rows
computed and shown, nothing written). The user gives ONE explicit GO; only then
the same command with `--commit`. Statuses (`pending/running/done/failed` in a
`X_status` column) are the checkpoint — re-running resumes the pending rows.

## §6 — One path in, one path out

- **Sourcing** (any external fetch producing many rows) → land a CSV on disk,
  then `db.py import-csv <table> <file> --key <col>`. Never mass `--rows` JSON.
- **Enrichment** → either (A) pass-through data the user already has, written
  as-is (`import-csv`, or a small `modify`), or (B) computed per row through
  `runner.py` → `agent.py`. One mode per run — never a third path (no per-row
  loops in the conversation, no hand-calling `agent.py` row by row).

## §7 — References & cost

- Reference other skills as slash commands, never as file paths: `/bricks:find`,
  `/bricks:enrich`, `/bricks:workspace`, `/bricks:gtm-onboard`,
  `/bricks:tools-guide`.
- The engine runs on the Claude **subscription** by default; prefer `haiku` for
  per-row work to spare the rate limits. Announce a batch's scope before you
  commit it.
