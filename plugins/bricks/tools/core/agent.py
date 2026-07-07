#!/usr/bin/env python3
"""ONE agent, ONE prompt, ONE answer — the unit brain of Bricks.

agent() is the single AI-calling function of the project: every model call
outside the session goes through it, whether fired directly (one row) or per
row by runner.py. Runs on the Claude Agent SDK (pip: claude-agent-sdk), which
drives the local `claude` CLI in-process: typed messages, native MCP,
guaranteed structured output.

Auth follows the SDK/CLI precedence (first found wins), inherited from
~/.bricks/env and the environment:
  1. ANTHROPIC_API_KEY        -> API billing (pay-per-token, opt-in)
  2. CLAUDE_CODE_OAUTH_TOKEN  -> the Claude SUBSCRIPTION (the default —
                                 generated once with `claude setup-token`)
  3. the interactive `claude` login (Keychain) -> subscription too

- web=False (default): the agent reasons ONLY on the prompt content — the
  row's data is injected in the prompt by the caller, never fetched.
- web=True: adds the Bright Data MCP (BRIGHTDATA_API_TOKEN), navigation
  capped by max_pages.
- schema=<JSON schema dict>: the answer is GUARANTEED to validate against it
  (SDK output_format) -> returns the parsed dict. schema=None -> raw text.

Callable both ways:
    from agent import agent
    python3 agent.py --prompt "..." [--web] [--schema '{...}'] [--model haiku]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

DEFAULT_TIMEOUT = 120
DEFAULT_MAX_PAGES = 5
BRIGHTDATA_URL = "https://mcp.brightdata.com/mcp?token={token}&pro=1"

AUTH_HINT = (
    "aucune authentification Claude trouvée — le moteur tourne sur ton "
    "ABONNEMENT par défaut : génère un token une fois avec `claude setup-token` "
    "puis stocke-le dans ~/.bricks/env (CLAUDE_CODE_OAUTH_TOKEN=<token>). "
    "Alternative facturée au token : ANTHROPIC_API_KEY.")


class AgentError(RuntimeError):
    """The agent could not be configured or could not produce an answer."""


# Self-load ~/.bricks/env before anything runs (subscription token, Bright Data
# token…). Same loader the front's settings panel writes to — one source of truth.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envfile  # noqa: E402
envfile.load()


def _sdk():
    try:
        import claude_agent_sdk
        return claude_agent_sdk
    except ImportError as exc:
        raise AgentError("claude-agent-sdk n'est pas installé — "
                         "pip3 install --user --break-system-packages claude-agent-sdk") from exc


def _with_auth_hint(message: str) -> str:
    has_cred = (os.environ.get("ANTHROPIC_API_KEY", "").strip()
                or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip())
    looks_auth = any(w in message.lower() for w in
                     ("auth", "credential", "login", "unauthor", "401", "api key"))
    if not has_cred and (looks_auth or "exit" in message.lower()):
        return f"{message}\n{AUTH_HINT}"
    return message


def agent(prompt: str, web: bool = False, schema: dict | None = None,
          model: str | None = None, max_pages: int = DEFAULT_MAX_PAGES,
          timeout: int = DEFAULT_TIMEOUT) -> str | dict:
    """Run ONE agent, return ONE answer (dict if schema, else str). Raises AgentError."""
    if not (prompt or "").strip():
        raise AgentError("empty prompt")
    sdk = _sdk()
    kwargs: dict = {"model": model or None, "max_turns": 4}
    if web:
        token = os.environ.get("BRIGHTDATA_API_TOKEN", "").strip()
        if not token:
            raise AgentError("web=True needs BRIGHTDATA_API_TOKEN in the environment "
                             "(~/.bricks/env)")
        kwargs["mcp_servers"] = {"brightdata": {
            "type": "http", "url": BRIGHTDATA_URL.format(token=token)}}
        kwargs["allowed_tools"] = ["mcp__brightdata__*"]
        kwargs["max_turns"] = max_pages * 2 + 4
    if schema:
        kwargs["output_format"] = {"type": "json_schema", "schema": schema}
    options = sdk.ClaudeAgentOptions(**kwargs)

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
        raise AgentError(_with_auth_hint(str(exc))) from exc
    except Exception as exc:  # CLINotFoundError, ProcessError, CLIConnectionError…
        raise AgentError(_with_auth_hint(f"{type(exc).__name__}: {str(exc)[:300]}")) from exc

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
