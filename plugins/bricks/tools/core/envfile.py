#!/usr/bin/env python3
"""Self-loading secrets for the engine — the desktop-proof lane.

Claude Code desktop runs tool subprocesses in a sandbox that cannot read the
macOS Keychain (where the interactive login lives) and does not always inherit
shell-profile exports. So the engine tools load their own keys from ONE file, at
import time, before anything else runs:

    ~/.bricks/env          (override path with BRICKS_ENV_FILE)

Format — one KEY=value per line, # comments allowed:

    CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat-…   # engine workers (claude setup-token)
    ANTHROPIC_API_KEY=…                     # opt-in, token billing
    FULLENRICH_API_KEY=…                    # people search (dashboard key)
    BRIGHTDATA_API_TOKEN=…                  # agent --web

Values already present in the environment are NEVER overridden. Missing file =
silent no-op. Keep the file at chmod 600; it lives outside every repo on purpose.

CLI (used by the front's settings panel, and by sessions when a key is missing):
    python3 envfile.py status              # which keys are set (values MASKED)
    python3 envfile.py set KEY VALUE       # store/replace one key (chmod 600)
"""

from __future__ import annotations

import json
import os
import stat
import sys

DEFAULT_PATH = "~/.bricks/env"

#: Keys the engine knows about — label + where to get them. Order = priority
#: shown to the user: the SUBSCRIPTION is the default worker auth; the API key
#: is the opt-in (higher, scalable rate limits).
KNOWN_KEYS = [
    {"key": "CLAUDE_CODE_OAUTH_TOKEN",
     "label": "Workers du moteur — abonnement Claude (par défaut)",
     "hint": "Terminal : claude setup-token"},
    {"key": "ANTHROPIC_API_KEY",
     "label": "Workers du moteur — clé API (optionnel, facturation au token)",
     "hint": "console.anthropic.com → API Keys"},
    {"key": "FULLENRICH_API_KEY",
     "label": "FullEnrich — recherche de contacts (API)",
     "hint": "app.fullenrich.com → Settings → API"},
    {"key": "BRIGHTDATA_API_TOKEN",
     "label": "Bright Data — web researcher",
     "hint": "brightdata.com → compte → API token"},
]


def env_path() -> str:
    return os.path.expanduser(os.environ.get("BRICKS_ENV_FILE", DEFAULT_PATH))


def _parse(path: str) -> dict:
    values = {}
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return values
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and "REMPLACE" not in value:
            values[key] = value
    return values


def load() -> None:
    """Load ~/.bricks/env into os.environ, never overriding an existing value."""
    for key, value in _parse(env_path()).items():
        if key not in os.environ:
            os.environ[key] = value


def status() -> dict:
    """Which known keys are configured — values MASKED (last 4 chars)."""
    stored = _parse(env_path())
    keys = []
    for entry in KNOWN_KEYS:
        value = stored.get(entry["key"]) or os.environ.get(entry["key"], "")
        value = value if "REMPLACE" not in value else ""
        keys.append({**entry, "set": bool(value),
                     "masked": ("…" + value[-4:]) if value else ""})
    return {"ok": True, "path": env_path(), "keys": keys}


def set_key(key: str, value: str) -> dict:
    """Store/replace one key in the env file (created chmod 600 if needed)."""
    key = (key or "").strip()
    value = (value or "").strip()
    if key not in {e["key"] for e in KNOWN_KEYS}:
        raise ValueError(f"unknown key {key!r} — known: {[e['key'] for e in KNOWN_KEYS]}")
    if not value or "REMPLACE" in value:
        raise ValueError("empty value")
    path = env_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        lines = []
    line = f"{key}={value}\n"
    replaced = False
    for i, existing in enumerate(lines):
        bare = existing.strip().lstrip("# ").strip()
        if bare.startswith(f"{key}="):
            lines[i] = line
            replaced = True
            break
    if not replaced:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(line)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 600
    os.environ[key] = value
    return {"ok": True, "key": key, "set": True, "masked": "…" + value[-4:]}


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    try:
        if args and args[0] == "status":
            print(json.dumps(status(), ensure_ascii=False))
        elif args and args[0] == "set" and len(args) == 3:
            print(json.dumps(set_key(args[1], args[2]), ensure_ascii=False))
        else:
            print(json.dumps({"ok": False,
                              "error": "usage: envfile.py status | set KEY VALUE"}),
                  file=sys.stderr)
            return 1
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
