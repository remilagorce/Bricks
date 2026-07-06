#!/usr/bin/env python3
"""Bricks front server — local web UI over the current workspace's database.

Serves the Clay-like table UI (index.html) plus a small JSON API that reuses
the plugin's own tools (tools/workspace.py and tools/db.py), so every
mutation goes through exactly the same code paths as the skills.

Run from the user's project root (the directory that contains ./bricks):
    python3 server.py [--port 4321] [--root bricks]

If the port is busy, the next free port is tried (up to +20). On success the
server prints the URL to open:  Bricks UI -> http://127.0.0.1:<port>

Endpoints:
    GET  /                          the UI
    GET  /api/ping                  {"app": "bricks"} — detect a running server
    GET  /api/status                same JSON as `workspace.py status`
    GET  /api/table/<name>          {"headers": [...], "rows": [[...], ...]}
    POST /api/table/<name>/remove   {"ids": ["a1b2...", ...]} — delete rows by _id
    POST /api/workspace/switch      {"name": "<workspace>"} — switch current workspace
    GET  /api/settings              engine keys status (~/.bricks/env) — values MASKED
    POST /api/settings              {"key": "...", "value": "..."} — store one key

Rows are addressed by the reserved `_id` column (INTEGER PRIMARY KEY),
never by row number: ids do not shift when the table changes underneath the
UI, so deletion is race-free. The front hides `_`-prefixed columns.

Binds to 127.0.0.1 only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

FRONT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(FRONT_DIR)
sys.path.insert(0, os.path.join(PLUGIN_ROOT, "tools"))  # workspace + db modules

import workspace as ws  # noqa: E402
import db as dbtool     # noqa: E402
import envfile          # noqa: E402

PORT_SCAN_RANGE = 20

ROOT = "bricks"  # overridden by --root in main()


class ApiError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def _db_path() -> str:
    """Resolve the current workspace's bricks.db, or raise ApiError."""
    status = ws.status(ROOT)
    if not status.get("initialized"):
        raise ApiError(409, "Bricks is not initialized here — run /bricks:workspace new <name>")
    if not status.get("currentWorkspace"):
        raise ApiError(409, "No current workspace — run /bricks:workspace new <name>")
    current = status.get("current")
    if not current:
        raise ApiError(409, status.get("warning", "current workspace is missing on disk"))
    path = current.get("db") or os.path.join(current["path"], dbtool.DB_FILENAME)
    if not os.path.isfile(path):
        raise ApiError(404, "no database yet in this workspace — run a find first")
    return path


def _read_table(name: str) -> dict:
    """Headers + rows (as strings) straight from the workspace database."""
    if not dbtool.IDENT_RE.match(name):
        raise ApiError(400, f"invalid table name: {name!r}")
    path = _db_path()
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise ApiError(500, f"cannot open database: {exc}") from None
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        if not exists:
            raise ApiError(404, f"table not found: {name}")
        cursor = conn.execute(f'SELECT * FROM "{name}"')
        headers = [c[0] for c in cursor.description]
        rows = [["" if v is None else str(v) for v in r] for r in cursor]
    finally:
        conn.close()
    return {"table": name, "headers": headers, "rows": rows}


def _switch_workspace(name) -> dict:
    """Switch the current workspace via the same code path as the skill."""
    if not isinstance(name, str) or not name.strip():
        raise ApiError(400, '"name" must be a non-empty string')
    try:
        ws.switch(ROOT, name)
    except ws.WorkspaceError as exc:
        raise ApiError(400, str(exc)) from None
    return ws.status(ROOT)


def _remove_rows(name: str, ids) -> dict:
    if not isinstance(ids, list) or not ids:
        raise ApiError(400, '"ids" must be a non-empty list of _id values')
    if not dbtool.IDENT_RE.match(name):
        raise ApiError(400, f"invalid table name: {name!r}")
    try:
        # All-or-nothing: unknown ids fail before anything is deleted.
        result = dbtool.remove(_db_path(), name, ids=ids)
    except dbtool.DbError as exc:
        raise ApiError(400, str(exc)) from None
    return {"ok": True, "table": name, "removed": result["removed"], "rows": result["rows"]}


def _set_setting(payload: dict) -> dict:
    """Store one engine key in ~/.bricks/env; the value is never echoed."""
    try:
        result = envfile.set_key(payload.get("key"), payload.get("value"))
    except ValueError as exc:
        raise ApiError(400, str(exc)) from None
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "BricksFront/0.1"

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_index(self) -> None:
        with open(os.path.join(FRONT_DIR, "index.html"), "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path in ("/", "/index.html"):
                self._send_index()
            elif path == "/api/ping":
                self._send_json(200, {"app": "bricks", "root": os.path.abspath(ROOT)})
            elif path == "/api/status":
                self._send_json(200, ws.status(ROOT))
            elif path == "/api/settings":
                self._send_json(200, envfile.status())
            elif path.startswith("/api/table/"):
                self._send_json(200, _read_table(path[len("/api/table/"):]))
            else:
                self._send_json(404, {"ok": False, "error": f"no such endpoint: {path}"})
        except ApiError as exc:
            self._send_json(exc.code, {"ok": False, "error": str(exc)})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        match = re.fullmatch(r"/api/table/([^/]+)/remove", path)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError as exc:
                raise ApiError(400, f"invalid JSON body: {exc}") from None
            if path == "/api/workspace/switch":
                self._send_json(200, _switch_workspace(payload.get("name")))
            elif path == "/api/settings":
                self._send_json(200, _set_setting(payload))
            elif match:
                self._send_json(200, _remove_rows(match.group(1), payload.get("ids")))
            else:
                raise ApiError(404, f"no such endpoint: {path}")
        except ApiError as exc:
            self._send_json(exc.code, {"ok": False, "error": str(exc)})

    def log_message(self, fmt: str, *args) -> None:
        pass  # keep background-task output quiet


def main(argv=None) -> int:
    global ROOT
    parser = argparse.ArgumentParser(description="Bricks front server (local only).")
    parser.add_argument("--port", type=int, default=4321)
    parser.add_argument("--root", default="bricks", help="Bricks data root (default: ./bricks)")
    args = parser.parse_args(argv)
    ROOT = args.root

    for port in range(args.port, args.port + PORT_SCAN_RANGE):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        except OSError:
            continue
        print(f"Bricks UI -> http://127.0.0.1:{port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()
        return 0

    print(json.dumps({"ok": False, "error": f"no free port in {args.port}..{args.port + PORT_SCAN_RANGE - 1}"}),
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())