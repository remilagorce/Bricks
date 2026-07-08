#!/usr/bin/env python3
"""Bricks workspaces — one directory per workspace, one `current` pointer.

Layout (data root ./bricks in the working directory, override with --root):
    bricks/
      config.json                {"current": "<slug>"}
      workspaces/<slug>/
        workspace.json           metadata: name, goal, createdAt, status
        bricks.db                the workspace database (via tools/core/db.py only)
        context/                 offer.md, icp.md, personas/ (copied from templates)
        staging/                 raw provisional payloads before commit to the db
        memory/
          state.json             structured pipeline state (cursors, steps done)
          NOTES.md               free-form working memory

This script owns config.json — skills never edit it by hand.

`new` and `switch` return a `banner` (a #### box with the workspace name)
plus a `welcome` line: skills display both to the user on every workspace
change — same banner the SessionStart hook shows at session open.

CLI (JSON on stdout; on error JSON on stderr + exit 1):
    python3 workspace.py [--root bricks] init      # create the root (idempotent)
    python3 workspace.py [--root bricks] new <name> [--goal "..."]
    python3 workspace.py [--root bricks] switch <name>
    python3 workspace.py [--root bricks] list
    python3 workspace.py [--root bricks] status

`new` creates the root on its own, so `init` is rarely needed by hand — it
exists as an explicit way to set up an empty root without a workspace yet. The
SessionStart hook never calls it: initialization is lazy, on the first GTM
action, so unrelated directories stay clean.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT_ROOT = "bricks"
DB_FILENAME = "bricks.db"
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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


def _ws_dir(root: str, slug: str) -> str:
    return os.path.join(root, "workspaces", slug)


def _read_config(root: str) -> dict:
    path = _config_path(root)
    if not os.path.isfile(path):
        return {}
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


def _write_config(root: str, config: dict) -> None:
    os.makedirs(root, exist_ok=True)
    _write_json(_config_path(root), config)


def _read_meta(root: str, slug: str) -> dict:
    """workspace.json metadata ({} if absent or unreadable — metadata is optional)."""
    path = os.path.join(_ws_dir(root, slug), "workspace.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _workspaces(root: str) -> list[str]:
    directory = os.path.join(root, "workspaces")
    if not os.path.isdir(directory):
        return []
    return sorted(e for e in os.listdir(directory)
                  if os.path.isdir(os.path.join(directory, e)) and not e.startswith("."))


def _tables(root: str, slug: str) -> list[str]:
    db_path = os.path.join(_ws_dir(root, slug), DB_FILENAME)
    if not os.path.isfile(db_path):
        return []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            return [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        finally:
            conn.close()
    except sqlite3.Error:
        return []


def _context_files(root: str, slug: str) -> list[str]:
    base = os.path.join(_ws_dir(root, slug), "context")
    found = []
    for dirpath, _dirs, files in os.walk(base):
        for f in sorted(files):
            if f.endswith(".md"):
                found.append(os.path.relpath(os.path.join(dirpath, f), _ws_dir(root, slug)))
    return sorted(found)


def banner(name: str) -> str:
    """A #### box with the workspace name centered — the workspace banner."""
    inner = max(len(name) + 12, 34)
    top = "#" * (inner + 4)
    pad = "#" + " " * (inner + 2) + "#"
    label = "#" + name.center(inner + 2) + "#"
    return "\n".join([top, pad, label, pad, top])


def _welcome(name: str) -> dict:
    """Banner payload for new/switch results and the session hook: the box, a
    welcome line, and the instruction that makes Claude render them to the user.
    (The receipt lands in Claude's context, not on screen — without the display
    instruction the nice box never reaches the user.)"""
    return {
        "banner": banner(name),
        "welcome": f"Bienvenue, tu es actuellement sur le workspace « {name} »",
        "display": ("Show the banner to the user VERBATIM inside a fenced code block, "
                    "immediately followed by the welcome line — before anything else. "
                    "Do this on every workspace change."),
    }


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def init(root: str = DEFAULT_ROOT) -> dict:
    """Create the Bricks root and config.json if missing. Idempotent — safe to
    call any time. Creates no workspace; it only makes the root exist so
    skills never have to check for it. The SessionStart hook never calls it:
    initialization stays lazy so unrelated directories stay clean."""
    existed = os.path.isfile(_config_path(root))
    os.makedirs(os.path.join(root, "workspaces"), exist_ok=True)
    if not existed:
        _write_config(root, {"current": None, "createdAt": _now()})
    return {"ok": True, "action": "init", "root": os.path.abspath(root),
            "alreadyInitialized": existed}


def new(name: str, root: str = DEFAULT_ROOT, goal: str | None = None) -> dict:
    init(root)
    slug = _slugify(name)
    ws_dir = _ws_dir(root, slug)
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
    with open(os.path.join(ws_dir, "memory", "NOTES.md"), "w", encoding="utf-8") as f:
        f.write(NOTES_TEMPLATE.format(name=slug))

    # The client brain: context/ scaffolded from the plugin templates.
    if os.path.isdir(CONTEXT_TEMPLATES):
        shutil.copytree(CONTEXT_TEMPLATES, os.path.join(ws_dir, "context"))
    else:
        os.makedirs(os.path.join(ws_dir, "context"), exist_ok=True)

    # The data bus: one SQLite database per workspace, WAL mode.
    import db as dbtool
    dbtool.init(os.path.join(ws_dir, DB_FILENAME))

    config = _read_config(root)
    config["current"] = slug
    _write_config(root, config)
    return {"ok": True, "action": "new", "current": slug, "goal": goal,
            "path": os.path.abspath(ws_dir),
            "db": os.path.abspath(os.path.join(ws_dir, DB_FILENAME)),
            "context": _context_files(root, slug), **_welcome(slug)}


def switch(name: str, root: str = DEFAULT_ROOT) -> dict:
    slug = _slugify(name)
    if not os.path.isdir(_ws_dir(root, slug)):
        raise WorkspaceError(
            f"workspace '{slug}' does not exist — available: {_workspaces(root) or 'none'}")
    config = _read_config(root)
    config["current"] = slug
    _write_config(root, config)
    return {"ok": True, "action": "switch", "current": slug,
            "goal": _read_meta(root, slug).get("goal"),
            "path": os.path.abspath(_ws_dir(root, slug)),
            "tables": _tables(root, slug), "context": _context_files(root, slug),
            **_welcome(slug)}


def list_ws(root: str = DEFAULT_ROOT) -> dict:
    current = _read_config(root).get("current")
    entries = []
    for n in _workspaces(root):
        meta = _read_meta(root, n)
        entries.append({"name": n, "goal": meta.get("goal"),
                        "createdAt": meta.get("createdAt"),
                        "tables": len(_tables(root, n)), "current": n == current})
    return {"ok": True, "current": current, "workspaces": entries}


def status(root: str = DEFAULT_ROOT) -> dict:
    current = _read_config(root).get("current")
    result: dict = {"ok": True, "initialized": os.path.isfile(_config_path(root)),
                    "root": os.path.abspath(root), "current": current,
                    "workspaces": _workspaces(root)}
    if current and current in result["workspaces"]:
        meta = _read_meta(root, current)
        result.update({"path": os.path.abspath(_ws_dir(root, current)),
                       "goal": meta.get("goal"),
                       "createdAt": meta.get("createdAt"),
                       "db": os.path.abspath(os.path.join(_ws_dir(root, current), DB_FILENAME)),
                       "tables": _tables(root, current),
                       "context": _context_files(root, current)})
    elif current:
        result["warning"] = f"current workspace '{current}' is missing on disk"
    else:
        result["hint"] = "no current workspace — run `new <name>`"
    return result


def current_db(root: str = DEFAULT_ROOT) -> str:
    """Absolute path of the current workspace's bricks.db (used by db.resolve)."""
    current = _read_config(root).get("current")
    if not current:
        raise WorkspaceError("no current workspace — run workspace.py new <name>")
    return os.path.abspath(os.path.join(_ws_dir(root, current), DB_FILENAME))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Manage Bricks workspaces (JSON output).")
    parser.add_argument("--root", default=DEFAULT_ROOT, help="data root (default: ./bricks)")
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
        if args.command == "new":
            result = new(args.name, args.root, args.goal)
        elif args.command == "switch":
            result = switch(args.name, args.root)
        elif args.command == "list":
            result = list_ws(args.root)
        elif args.command == "init":
            result = init(args.root)
        else:
            result = status(args.root)
    except WorkspaceError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
