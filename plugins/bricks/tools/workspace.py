#!/usr/bin/env python3
"""Bricks workspace manager — creates, switches and inspects Bricks workspaces.

The data root is ./bricks in the current working directory (override with
--root). This script owns config.json — skills never edit it by hand.

Layout managed:
    bricks/
      config.json                      { "currentWorkspace": "<name>", ... }
      workspaces/<name>/
        workspace.json                 metadata: name, goal, createdAt, status
        bricks.db                      SQLite database — THE data bus (via tools/db.py only)
        context/                       the client brain — offer.md, icp.md, personas/
        staging/                       raw provisional payloads before commit to the db
        memory/
          state.json                   structured pipeline state (cursors, steps done)
          NOTES.md                     free-form working memory

`new` and `switch` return a `banner` (a #### box with the workspace name)
plus a `welcome` line: skills display both to the user on every workspace
change — same banner the SessionStart hook shows at session open.

CLI (JSON on stdout; on error: JSON on stderr + exit 1):
    python3 workspace.py status
    python3 workspace.py init
    python3 workspace.py new <name> [--goal "..."]
    python3 workspace.py switch <name>
    python3 workspace.py list

All commands are idempotent where it makes sense: `init` on an initialized
root is a no-op, `new` auto-initializes the root first.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CONFIG_VERSION = 1
DEFAULT_ROOT = "bricks"
DB_FILENAME = "bricks.db"
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTEXT_TEMPLATES = os.path.join(PLUGIN_ROOT, "templates", "context")

NOTES_TEMPLATE = """\
# Working notes — {name}

> Free-form working memory for this workspace. Skills append decisions,
> context and open questions here, newest entries at the bottom.
"""


class WorkspaceError(ValueError):
    """Raised on any invalid workspace operation."""


# --------------------------------------------------------------------------
# Internals
# --------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not slug:
        raise WorkspaceError(f"cannot derive a valid workspace name from {name!r}")
    return slug


def _config_path(root: str) -> str:
    return os.path.join(root, "config.json")


def _workspaces_dir(root: str) -> str:
    return os.path.join(root, "workspaces")


def _workspace_dir(root: str, name: str) -> str:
    return os.path.join(_workspaces_dir(root), name)


def _read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkspaceError(f"cannot read {path}: {exc}") from None


def _write_json(path: str, data: dict) -> None:
    """Atomic JSON write (temp file + rename)."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".bricks-", suffix=".json.tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _require_config(root: str) -> dict:
    path = _config_path(root)
    if not os.path.isfile(path):
        raise WorkspaceError(
            f"Bricks root not initialized at {os.path.abspath(root)} "
            f"(no config.json) — run `init` or `new <name>` first"
        )
    return _read_json(path)


def _existing_workspaces(root: str) -> list[str]:
    directory = _workspaces_dir(root)
    if not os.path.isdir(directory):
        return []
    return sorted(
        entry for entry in os.listdir(directory)
        if os.path.isdir(os.path.join(directory, entry)) and not entry.startswith(".")
    )


def _tables(root: str, name: str) -> list[str]:
    """Table names in the workspace's bricks.db (empty if no database yet)."""
    db_path = os.path.join(_workspace_dir(root, name), DB_FILENAME)
    if not os.path.isfile(db_path):
        return []
    import sqlite3
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            return [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )]
        finally:
            conn.close()
    except sqlite3.Error:
        return []


def _context_files(root: str, name: str) -> list[str]:
    """Relative paths of the context files present in the workspace."""
    base = os.path.join(_workspace_dir(root, name), "context")
    if not os.path.isdir(base):
        return []
    found = []
    for dirpath, _dirs, files in os.walk(base):
        for f in sorted(files):
            if f.endswith(".md"):
                full = os.path.join(dirpath, f)
                found.append(os.path.relpath(full, _workspace_dir(root, name)))
    return sorted(found)


def banner(name: str) -> str:
    """A #### box with the workspace name centered — the workspace banner."""
    inner = max(len(name) + 12, 34)
    top = "#" * (inner + 4)
    pad = "#" + " " * (inner + 2) + "#"
    label = "#" + name.center(inner + 2) + "#"
    return "\n".join([top, pad, label, pad, top])


def _welcome(slug: str) -> dict:
    """Banner payload attached to new/switch results and the session hook."""
    return {
        "banner": banner(slug),
        "welcome": f"Bienvenue, tu es actuellement sur le workspace « {slug} »",
        "display": (
            "Show the banner to the user VERBATIM inside a fenced code block, "
            "immediately followed by the welcome line — before anything else. "
            "Do this on every workspace change."
        ),
    }


def _set_current(root: str, name: str | None) -> None:
    config = _require_config(root)
    config["currentWorkspace"] = name
    config["updatedAt"] = _now()
    _write_json(_config_path(root), config)


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def status(root: str) -> dict:
    if not os.path.isfile(_config_path(root)):
        return {
            "initialized": False,
            "root": os.path.abspath(root),
            "hint": "run `init` to initialize, or `new <name>` to create a first workspace",
        }
    config = _require_config(root)
    current = config.get("currentWorkspace")
    workspaces = _existing_workspaces(root)
    result: dict = {
        "initialized": True,
        "root": os.path.abspath(root),
        "currentWorkspace": current,
        "workspaces": workspaces,
    }
    if current is None:
        result["hint"] = "no current workspace — run `new <name>` or `switch <name>`"
    elif current not in workspaces:
        result["warning"] = f"current workspace '{current}' is missing on disk"
    else:
        meta_path = os.path.join(_workspace_dir(root, current), "workspace.json")
        meta = _read_json(meta_path) if os.path.isfile(meta_path) else {}
        result["current"] = {
            "path": os.path.abspath(_workspace_dir(root, current)),
            "goal": meta.get("goal"),
            "createdAt": meta.get("createdAt"),
            "tables": _tables(root, current),
            "db": os.path.join(_workspace_dir(root, current), DB_FILENAME),
            "context": _context_files(root, current),
        }
    return result


def init(root: str) -> dict:
    os.makedirs(_workspaces_dir(root), exist_ok=True)
    config_path = _config_path(root)
    if os.path.isfile(config_path):
        return {"ok": True, "action": "init", "root": os.path.abspath(root),
                "alreadyInitialized": True}
    _write_json(config_path, {
        "version": CONFIG_VERSION,
        "currentWorkspace": None,
        "createdAt": _now(),
    })
    return {"ok": True, "action": "init", "root": os.path.abspath(root),
            "alreadyInitialized": False}


def new(root: str, name: str, goal: str | None = None) -> dict:
    init(root)
    slug = _slugify(name)
    ws_dir = _workspace_dir(root, slug)
    if os.path.isdir(ws_dir):
        raise WorkspaceError(f"workspace '{slug}' already exists — use `switch {slug}`")

    for sub in ("staging", "memory"):
        os.makedirs(os.path.join(ws_dir, sub), exist_ok=True)
    _write_json(os.path.join(ws_dir, "workspace.json"), {
        "name": slug,
        "goal": goal,
        "createdAt": _now(),
        "status": "active",
    })
    _write_json(os.path.join(ws_dir, "memory", "state.json"), {})
    notes_path = os.path.join(ws_dir, "memory", "NOTES.md")
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write(NOTES_TEMPLATE.format(name=slug))

    # The client brain: context/ scaffolded from the plugin templates.
    context_dir = os.path.join(ws_dir, "context")
    if os.path.isdir(CONTEXT_TEMPLATES):
        shutil.copytree(CONTEXT_TEMPLATES, context_dir)
    else:
        os.makedirs(context_dir, exist_ok=True)

    # The data bus: one SQLite database per workspace, WAL mode.
    import db as dbtool
    dbtool.init(os.path.join(ws_dir, DB_FILENAME))

    _set_current(root, slug)
    result = {"ok": True, "action": "new", "workspace": slug, "goal": goal,
              "path": os.path.abspath(ws_dir), "currentWorkspace": slug,
              "context": _context_files(root, slug),
              "db": os.path.abspath(os.path.join(ws_dir, DB_FILENAME))}
    result.update(_welcome(slug))
    return result


def switch(root: str, name: str) -> dict:
    _require_config(root)
    slug = _slugify(name)
    if not os.path.isdir(_workspace_dir(root, slug)):
        available = _existing_workspaces(root)
        raise WorkspaceError(
            f"workspace '{slug}' does not exist — available: {available or 'none'}"
        )
    _set_current(root, slug)
    result = {"ok": True, "action": "switch", "currentWorkspace": slug,
              "path": os.path.abspath(_workspace_dir(root, slug)),
              "tables": _tables(root, slug),
              "context": _context_files(root, slug)}
    result.update(_welcome(slug))
    return result


def list_workspaces(root: str) -> dict:
    if not os.path.isfile(_config_path(root)):
        return {"initialized": False, "root": os.path.abspath(root), "workspaces": []}
    config = _require_config(root)
    current = config.get("currentWorkspace")
    entries = []
    for name in _existing_workspaces(root):
        meta_path = os.path.join(_workspace_dir(root, name), "workspace.json")
        meta = _read_json(meta_path) if os.path.isfile(meta_path) else {}
        entries.append({
            "name": name,
            "goal": meta.get("goal"),
            "createdAt": meta.get("createdAt"),
            "tables": len(_tables(root, name)),
            "current": name == current,
        })
    return {"initialized": True, "currentWorkspace": current, "workspaces": entries}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Manage Bricks workspaces and config.json (JSON output)."
    )
    parser.add_argument("--root", default=DEFAULT_ROOT,
                        help="Bricks data root (default: ./bricks)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show initialization state and current workspace")
    sub.add_parser("init", help="create the Bricks root and config.json if missing")
    sub.add_parser("list", help="list workspaces with metadata")

    p_new = sub.add_parser("new", help="create a workspace and make it current")
    p_new.add_argument("name", help="workspace name (will be slugified)")
    p_new.add_argument("--goal", default=None, help="one-line goal for the workspace")

    p_switch = sub.add_parser("switch", help="set the current workspace")
    p_switch.add_argument("name", help="existing workspace name")

    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            result = status(args.root)
        elif args.command == "init":
            result = init(args.root)
        elif args.command == "new":
            result = new(args.root, args.name, args.goal)
        elif args.command == "switch":
            result = switch(args.root, args.name)
        else:
            result = list_workspaces(args.root)
    except WorkspaceError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())