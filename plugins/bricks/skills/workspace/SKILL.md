---
name: workspace
description: Create, switch, list and inspect Bricks workspaces — the project/client containers that hold a database and context (offer, ICP, personas). Use when the user says "workspace", "nouveau workspace", "switch workspace", "où j'en suis", or when another skill needs a workspace and none exists.
argument-hint: "new <name> | switch <name> | list | status | (nothing)"
---

# Workspace — create, switch, inspect

Manages the Bricks data root (`bricks/` in the current working directory) and
the current-workspace pointer in `bricks/config.json`. Never create or edit
these files by hand — always through the tool:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/workspace.py" <command>
```

Every command prints JSON.

## Commands

| User intent | Run |
|---|---|
| Where am I / current state | `status` |
| Create a workspace | `new <name>` (slugified, becomes current) |
| Change current workspace | `switch <name>` |
| See all workspaces | `list` |

## Behavior rules

- **No argument given** → run `status` and report: current workspace (or its
  absence), tables, and context files present. Adapt from there.
- **No current workspace, and the request implies one** (a client, campaign
  or project name in the message) → run `new <slug>` directly, don't ask
  first. If no name is implied, ask for one.
- **After `new`** → the workspace has fresh `context/` files (`offer.md`,
  `icp.md`, `personas/`) still empty (TODO placeholders) and an empty
  database. Hand off immediately to `/bricks:gtm-onboard` to discover and
  fill the ICP — do not fill `context/` by hand here.
- **Drift guardrail** — if the request contradicts the current workspace's
  `context/` (different product, different ICP, different target), STOP and
  ask: switch to another workspace, create a new one, or update the context?
- **`new` on an existing name** fails cleanly — relay the error and suggest
  `switch <name>` instead.
- Names are slugified automatically (`"Acme Outbound"` → `acme-outbound`);
  confirm the final slug to the user.

## Not in this skill

Filling `context/icp.md` and `context/offer.md` is `/bricks:gtm-onboard`'s
job, not this skill's. `workspace` only manages the container (which
database, which context files exist) — never their content.
