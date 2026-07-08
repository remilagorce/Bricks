---
name: workspace
description: Create, switch, list and inspect Bricks workspaces — the project/client containers that hold a database and context (offer, ICP, personas). Use when the user says "workspace", "new workspace", "nouveau workspace", "switch workspace", "change de workspace", "où j'en suis", or when another skill needs a workspace and none exists.
argument-hint: "new <name> | switch <name> | list | status | (nothing)"
---

# Workspace — create, switch, inspect

**Before anything, read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`** — the shared
contract every skill obeys (§2 covers workspace resolution).

Manages the Bricks data root (`bricks/` in the current working directory) and
the current-workspace pointer in `bricks/config.json`. Never create or edit
these files by hand — always through the tool:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/workspace.py" <command>
```

Every command prints JSON. The root is created LAZILY (§2): nothing exists
just from opening a session — `new` creates the root along with the first
workspace, no separate init step.

## Commands

| User intent | Run |
|---|---|
| Where am I / current state | `status` |
| Create a workspace | `new <name> [--goal "…"]` (slugified, becomes current; the goal shows in `status` and the session banner) |
| Change current workspace | `switch <name>` |
| See all workspaces | `list` |

## Banner ritual (mandatory)

`new` and `switch` return a `banner` (a `####` box with the workspace name), a
`welcome` line and a `display` instruction. After EVERY successful `new` or
`switch`, before anything else, show the user:

1. the `banner` value VERBATIM inside a fenced code block,
2. then the `welcome` line.

The receipt lands in your context, not on the user's screen — so you must
reproduce the box yourself. The SessionStart hook shows the same banner at
session open — the user must always know which world they are in.

## Behavior rules

- **No argument given** → run `status` and report: current workspace (or its
  absence), tables, and context files present. Adapt from there.
- **No current workspace, and the request implies one** (a client, campaign
  or project name in the message) → run `new <slug> --goal "…"` directly
  (goal = the user's stated objective, one line), don't ask first. If no
  name is implied, ask for one.
- **After `new`** → the workspace has fresh `context/` files (`offer.md`,
  `icp.md`, `personas/`) still empty (TODO placeholders) and an empty
  database. Hand off immediately to `/bricks:gtm-onboard` to discover and
  fill the ICP — it is the brick that infers, challenges and (via
  `/bricks:context-write`) fills the context; do not fill `context/` by hand
  here. Any objective the user stated feeds that onboarding, not a flag. If
  the user declines onboarding for now, leave the TODO placeholders and move
  on.
- **Drift guardrail** — if the request contradicts the current workspace's
  `context/` (different product, different ICP, different target), STOP and
  ask: switch to another workspace, create a new one, or update the context?
  See CONVENTIONS §3.
- **`new` on an existing name** fails cleanly — relay the error and suggest
  `switch <name>` instead.
- Names are slugified automatically (`"Acme Outbound"` → `acme-outbound`);
  confirm the final slug to the user.

## Not in this skill

Filling `context/icp.md` and `context/offer.md` is `/bricks:gtm-onboard`'s
job, not this skill's. `workspace` only manages the container (which
database, which context files exist) — never their content.
