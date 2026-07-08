"""Detect whether engine workers can inherit the parent Claude Code session."""

from __future__ import annotations

import os


def has_env_auth() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()
                or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip())


def in_plugin_session() -> bool:
    root = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    return bool(root and os.path.isdir(root))


def plugin_root() -> str | None:
    root = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    return root if root and os.path.isdir(root) else None


def subprocess_auth_env() -> dict[str, str]:
    """Env overrides for the SDK child.

    Do NOT redirect ``CLAUDE_CONFIG_DIR`` — that breaks macOS Keychain auth
    (the CLI looks up credentials under a service name derived from the config
    dir). When no explicit token is in the environment, the child must use the
    same default config dir as an interactive ``claude -p`` invocation.
    """
    return {}
