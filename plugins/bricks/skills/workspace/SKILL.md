---
name: workspace
description: Manage Bricks GTM workspaces — create, switch, list, inspect. Use when the user says "workspace", "new workspace", "switch workspace", "change de workspace", "où j'en suis", or when any Bricks skill needs a workspace and none exists.
argument-hint: "new <name> | switch <name> | list | status | (nothing)"
---

# Bricks workspace

Manages the Bricks data root (`bricks/` in the current working directory)
and the current-workspace pointer in `bricks/config.json`. All operations go
through the workspace tool — never create or edit these files by hand:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workspace.py" <command>
```

Every command prints JSON. Read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` for
the full data-layout contract.

## Commands

| User intent | Run |
| --- | --- |
| Create a workspace | `new <name> --goal "<one-line goal>"` (also makes it current) |
| Change current workspace | `switch <name>` |
| See all workspaces | `list` |
| Where am I / current state | `status` |

## Banner ritual (mandatory)

`new` and `switch` return a `banner` (a `####` box with the workspace name)
and a `welcome` line. After EVERY successful `new` or `switch`, show the
user, before anything else:

1. the `banner` value VERBATIM inside a fenced code block,
2. then the `welcome` line (e.g. « Bienvenue, tu es actuellement sur le
   workspace **acme-outbound** »).

The SessionStart hook shows the same banner at session open — the user must
always know which world they are in.

## Behavior rules

- **No argument given** → run `status` and report: initialized or not,
  current workspace, its goal, tables and context files. Adapt from there.
- **Not initialized** (`initialized: false`) → run `init` automatically,
  without asking. It only creates `bricks/config.json`.
- **No workspace yet** → if the user's request implies a name (client,
  campaign, ICP), run `new` with it; otherwise ask for a name. Always pass
  `--goal` when the user has stated an objective — other skills read it to
  pick up context.
- **After `new`** → the workspace is scaffolded with `context/` (offer.md,
  icp.md, personas/) and an empty `bricks.db`. Offer to fill the context
  now with three quick questions: what do you sell (one sentence)? who is
  the ideal customer? any hard disqualifiers (size, country…)? Write the
  answers into `context/offer.md` and `context/icp.md` (kill rules
  section). If the user prefers later, leave the TODO placeholders.
- **Drift guardrail** — if the user's request contradicts the current
  workspace's `context/` (another product, another ICP), STOP and ask:
  switch, new workspace, or update the context? See CONVENTIONS §3.
- **`new` on an existing name** fails cleanly — relay the message and offer
  `switch` instead.
- Names are slugified automatically (`"Acme Outbound"` → `acme-outbound`);
  report the final slug to the user.
