#!/usr/bin/env python3
"""Bricks workspaces — one directory per workspace, one `current` pointer.

Layout (data root ./bricks in the working directory, override with --root):
    bricks/
      config.json                {"current": "<slug>"}
      workspaces/<slug>/
        bricks.db                the workspace database (via tools/core/db.py only)
        context/                 offer.md, icp.md, personas/ (copied from templates)

This script owns config.json — skills never edit it by hand.

CLI (JSON on stdout; on error JSON on stderr + exit 1):
    python3 workspace.py [--root bricks] init      # create the root (idempotent)
    python3 workspace.py [--root bricks] new <name>
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

DEFAULT_ROOT = "bricks"
DB_FILENAME = "bricks.db"
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONTEXT_TEMPLATES = os.path.join(PLUGIN_ROOT, "templates", "context")


class WorkspaceError(ValueError):
    """Raised on any invalid workspace operation."""


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
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_config(root: str, config: dict) -> None:
    os.makedirs(root, exist_ok=True)
    tmp = _config_path(root) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, _config_path(root))


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


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def init(root: str = DEFAULT_ROOT) -> dict:
    """Create the Bricks root and config.json if missing. Idempotent — safe to
    call on every session start (SessionStart hook). Creates no workspace; it
    only makes the root exist so skills never have to check for it."""
    existed = os.path.isfile(_config_path(root))
    os.makedirs(os.path.join(root, "workspaces"), exist_ok=True)
    if not existed:
        _write_config(root, {"current": None})
    return {"ok": True, "action": "init", "root": os.path.abspath(root),
            "alreadyInitialized": existed}


def new(name: str, root: str = DEFAULT_ROOT) -> dict:
    slug = _slugify(name)
    ws_dir = _ws_dir(root, slug)
    if os.path.isdir(ws_dir):
        raise WorkspaceError(f"workspace '{slug}' already exists — use `switch {slug}`")
    if os.path.isdir(CONTEXT_TEMPLATES):
        shutil.copytree(CONTEXT_TEMPLATES, os.path.join(ws_dir, "context"))
    else:
        os.makedirs(os.path.join(ws_dir, "context"), exist_ok=True)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import db as dbtool
    dbtool.init(os.path.join(ws_dir, DB_FILENAME))
    config = _read_config(root)
    config["current"] = slug
    _write_config(root, config)
    return {"ok": True, "action": "new", "current": slug,
            "path": os.path.abspath(ws_dir),
            "db": os.path.abspath(os.path.join(ws_dir, DB_FILENAME)),
            "context": _context_files(root, slug)}


def switch(name: str, root: str = DEFAULT_ROOT) -> dict:
    slug = _slugify(name)
    if not os.path.isdir(_ws_dir(root, slug)):
        raise WorkspaceError(
            f"workspace '{slug}' does not exist — available: {_workspaces(root) or 'none'}")
    config = _read_config(root)
    config["current"] = slug
    _write_config(root, config)
    return {"ok": True, "action": "switch", "current": slug,
            "path": os.path.abspath(_ws_dir(root, slug)),
            "tables": _tables(root, slug), "context": _context_files(root, slug)}


def list_ws(root: str = DEFAULT_ROOT) -> dict:
    current = _read_config(root).get("current")
    return {"ok": True, "current": current,
            "workspaces": [{"name": n, "tables": len(_tables(root, n)),
                            "current": n == current} for n in _workspaces(root)]}


def status(root: str = DEFAULT_ROOT) -> dict:
    current = _read_config(root).get("current")
    result: dict = {"ok": True, "initialized": os.path.isfile(_config_path(root)),
                    "root": os.path.abspath(root), "current": current,
                    "workspaces": _workspaces(root)}
    if current and current in result["workspaces"]:
        result.update({"path": os.path.abspath(_ws_dir(root, current)),
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
    for cmd in ("new", "switch"):
        p = sub.add_parser(cmd)
        p.add_argument("name")
    sub.add_parser("list")
    sub.add_parser("status")
    sub.add_parser("init")
    args = parser.parse_args(argv)
    try:
        if args.command == "new":
            result = new(args.name, args.root)
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
