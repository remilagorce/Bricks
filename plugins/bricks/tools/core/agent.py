#!/usr/bin/env python3
"""ONE agent, ONE prompt, ONE answer — the unit brain of Bricks.

agent() is the single AI-calling function of the project: every model call
outside the session goes through it, whether fired directly (one row) or per
row by runner.py. Runs on the Claude Agent SDK (pip: claude-agent-sdk), which
drives the local `claude` CLI in-process: typed messages, native MCP,
guaranteed structured output.

Inside a Claude Code session (``CLAUDE_PLUGIN_ROOT`` set), workers inherit the
same subscription (Keychain / env) — but NOT the session's MCP servers or
settings (``strict_mcp_config`` + ``setting_sources=[]``): a disposable worker
gets exactly the tools it asks for (Bright Data when ``web=True``, nothing
otherwise), never whatever happens to be configured in the calling session or
project. Standalone (no session): falls back to ``~/.bricks/env`` for auth and
builds the same inline Bright Data MCP when ``web=True``.

- web=False: reasons only on the prompt — row data is injected, never fetched.
- web=True: Bright Data MCP, navigation capped by max_pages.
- schema=<JSON schema dict>: guaranteed structured output.

Callable both ways:
    from agent import agent
    python3 agent.py --prompt "..." [--web] [--schema '{...}'] [--model haiku]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys

DEFAULT_TIMEOUT = 120
DEFAULT_MAX_PAGES = 5
BRIGHTDATA_URL = "https://mcp.brightdata.com/mcp?token={token}&pro=1"

AUTH_HINT = (
    "le worker n'a pas pu réutiliser l'auth de la session — vérifie que tu es "
    "connecté dans Claude Code, ou stocke un token dans ~/.bricks/env "
    "(CLAUDE_CODE_OAUTH_TOKEN via `claude setup-token`, ou ANTHROPIC_API_KEY)."
)

INIT_HINT = (
    "Control request timeout: initialize — le sous-processus n'a pas pu "
    "s'authentifier ni charger les MCP. Relance depuis une session Claude Code "
    "connectée, ou configure ~/.bricks/env."
)


class AgentError(RuntimeError):
    """The agent could not be configured or could not produce an answer."""


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envfile  # noqa: E402
import session_auth  # noqa: E402

envfile.load()


def _sdk():
    try:
        import claude_agent_sdk
        return claude_agent_sdk
    except ImportError as exc:
        py = f"{sys.version_info.major}.{sys.version_info.minor}"
        raise AgentError(
            "claude-agent-sdk n'est pas installé — pip3 install --user "
            "--break-system-packages claude-agent-sdk (nécessite Python >= 3.10 ; "
            f"ce process tourne en {py} — lance les tools avec python3.12 le cas "
            "échéant). Alternative sans SDK : BRICKS_AGENT_TRANSPORT=api "
            "(crédits API, ANTHROPIC_API_KEY dans ~/.bricks/env).") from exc


def _auth_hint(message: str) -> str:
    low = message.lower()
    if "initialize" in low or "control request timeout" in low:
        return f"{message}\n{INIT_HINT}"
    looks_auth = any(w in low for w in
                     ("auth", "credential", "login", "unauthor", "401", "api key"))
    if not session_auth.has_env_auth() and (looks_auth or "exit" in low):
        return f"{message}\n{AUTH_HINT}"
    return message


def _build_options(sdk, *, web: bool, schema: dict | None, model: str | None,
                   max_pages: int):
    """Session mode: plugin MCP + settings. Standalone: inline Bright Data."""
    kwargs: dict = {
        "model": model or None,
        "max_turns": (max_pages * 2 + 4) if web else 4,
        "permission_mode": "bypassPermissions",
        "cwd": os.getcwd(),
        "tools": [],
        # Without this the child CLI also loads the CALLER's own project/user
        # MCP servers and settings (a totally unrelated MCP server from the
        # parent session, or a second same-named "brightdata"/"fullenrich"
        # entry with an unresolved ${TOKEN} placeholder) on top of what we
        # build below — silently colliding with it and causing the
        # "Control request timeout: initialize" failure (see INIT_HINT).
        "strict_mcp_config": True,
        "setting_sources": [],
    }
    plugin = session_auth.plugin_root()
    if plugin:
        kwargs["plugins"] = [{"type": "local", "path": plugin}]
    if web:
        token = os.environ.get("BRIGHTDATA_API_TOKEN", "").strip()
        if not token:
            raise AgentError(
                "web=True needs BRIGHTDATA_API_TOKEN — connect Bright Data via "
                "/mcp in the session, or set it in ~/.bricks/env")
        kwargs["mcp_servers"] = {"brightdata": {
            "type": "http", "url": BRIGHTDATA_URL.format(token=token)}}
        kwargs["allowed_tools"] = ["mcp__brightdata__*"]
    if schema:
        kwargs["output_format"] = {"type": "json_schema", "schema": schema}
    auth_env = session_auth.subprocess_auth_env()
    if auth_env:
        kwargs["env"] = auth_env
    cli = shutil.which("claude")
    if cli:
        kwargs["cli_path"] = cli
    return sdk.ClaudeAgentOptions(**kwargs)


def agent(prompt: str, web: bool = False, schema: dict | None = None,
          model: str | None = None, max_pages: int = DEFAULT_MAX_PAGES,
          timeout: int = DEFAULT_TIMEOUT) -> str | dict:
    """Run ONE agent, return ONE answer (dict if schema, else str). Raises AgentError."""
    if not (prompt or "").strip():
        raise AgentError("empty prompt")
    # BRICKS_AGENT_TRANSPORT=api routes the SAME call through the Anthropic
    # Messages API (agent_api.py) — for machines where the SDK stack cannot
    # run (Bun requires AVX). API credits instead of the subscription.
    if os.environ.get("BRICKS_AGENT_TRANSPORT", "").strip().lower() == "api":
        import agent_api
        try:
            return agent_api.agent_api(prompt, web=web, schema=schema,
                                       model=model, max_pages=max_pages,
                                       timeout=timeout)
        except agent_api.AgentApiError as exc:
            raise AgentError(str(exc)) from exc
    sdk = _sdk()
    options = _build_options(sdk, web=web, schema=schema, model=model,
                             max_pages=max_pages)

    async def _consume():
        final = None
        async for message in sdk.query(prompt=prompt, options=options):
            if isinstance(message, sdk.ResultMessage):
                final = message
        if final is None:
            raise AgentError("the agent ended without a ResultMessage")
        if final.is_error or final.subtype != "success":
            detail = "; ".join(final.errors or []) or (final.result or "")
            raise AgentError(f"agent {final.subtype}: {str(detail)[:300]}")
        return final

    try:
        final = asyncio.run(asyncio.wait_for(_consume(), timeout=timeout))
    except asyncio.TimeoutError as exc:
        raise AgentError(f"agent timed out after {timeout}s") from exc
    except AgentError as exc:
        raise AgentError(_auth_hint(str(exc))) from exc
    except Exception as exc:
        raise AgentError(_auth_hint(f"{type(exc).__name__}: {str(exc)[:300]}")) from exc

    output = final.structured_output if schema else final.result
    if output is None:
        raise AgentError("the agent returned no output")
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="One agent, one prompt, one answer (Claude Agent SDK).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prompt")
    group.add_argument("--prompt-file")
    parser.add_argument("--web", action="store_true", help="allow Bright Data web research")
    parser.add_argument("--schema", default=None, metavar="'{JSON}'",
                        help="JSON schema — the answer is guaranteed to validate against it")
    parser.add_argument("--model", default=None, help="model alias or id (e.g. haiku)")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args(argv)
    try:
        prompt = args.prompt
        if args.prompt_file:
            with open(args.prompt_file, encoding="utf-8") as f:
                prompt = f.read()
        schema = json.loads(args.schema) if args.schema else None
        output = agent(prompt, web=args.web, schema=schema, model=args.model,
                       max_pages=args.max_pages, timeout=args.timeout)
    except (AgentError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False),
              file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "output": output}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
