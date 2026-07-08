#!/usr/bin/env python3
"""API transport for agent.py — same contract, no Claude Agent SDK.

agent.py's default transport drives the local `claude` CLI through the
Claude Agent SDK (subscription billing). On machines where that stack
cannot run (the SDK's Bun runtime requires AVX), or when the caller
explicitly opts in with BRICKS_AGENT_TRANSPORT=api, this module answers
the SAME calls through the Anthropic Messages API directly:

    agent_api(prompt, web=False, schema=None, model=None,
              max_pages=5, timeout=120) -> str | dict

- web=True  : Bright Data via the API's remote MCP connector — the tool
              loop runs server-side, no per-row MCP handshake.
- schema    : guaranteed JSON via structured outputs (output_config.format).

Billing note: this path runs on the Anthropic API (API credits), NOT the
Claude subscription — that is the trade for skipping the CLI/SDK stack.
Env: ANTHROPIC_API_KEY (from ~/.bricks/env via envfile), BRIGHTDATA_API_TOKEN
for web=True. Model aliases: haiku/sonnet/opus → current model ids;
default haiku (CONVENTIONS §7 — spare the limits on per-row work).
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envfile  # noqa: E402

envfile.load()

MODEL_ALIASES = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-4-8",
}
DEFAULT_MODEL = "claude-haiku-4-5"
BRIGHTDATA_URL = "https://mcp.brightdata.com/mcp?token={token}&pro=1"
MCP_BETA = "mcp-client-2025-11-20"


class AgentApiError(RuntimeError):
    """The API transport could not be configured or produce an answer."""


def resolve_model(raw: str | None) -> str:
    raw = (raw or "").strip()
    return MODEL_ALIASES.get(raw, raw) if raw else DEFAULT_MODEL


def _strictify(schema: dict) -> dict:
    """Structured outputs require additionalProperties:false + required."""
    out = dict(schema)
    props = out.get("properties") or {}
    out.setdefault("type", "object")
    out.setdefault("additionalProperties", False)
    out.setdefault("required", list(props))
    return out


def _text(resp) -> str:
    return "".join(b.text for b in resp.content
                   if getattr(b, "type", None) == "text").strip()


def _client(timeout: int):
    try:
        import anthropic
    except ImportError as exc:
        raise AgentApiError("le transport API a besoin du SDK anthropic — "
                            "pip3 install --user --break-system-packages "
                            "anthropic") from exc
    return anthropic.Anthropic(timeout=float(timeout))


def agent_api(prompt: str, web: bool = False, schema: dict | None = None,
              model: str | None = None, max_pages: int = 5,
              timeout: int = 120) -> str | dict:
    """One prompt, one answer (dict if schema, else str). Raises AgentApiError."""
    if not (prompt or "").strip():
        raise AgentApiError("empty prompt")
    client = _client(timeout)
    model_id = resolve_model(model)
    kwargs: dict = {"model": model_id, "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}]}
    if schema:
        kwargs["output_config"] = {
            "format": {"type": "json_schema", "schema": _strictify(schema)}}

    try:
        if web:
            token = os.environ.get("BRIGHTDATA_API_TOKEN", "").strip()
            if not token:
                raise AgentApiError(
                    "web=True needs BRIGHTDATA_API_TOKEN — connect Bright Data "
                    "via /mcp in the session, or set it in ~/.bricks/env")
            kwargs["betas"] = [MCP_BETA]
            kwargs["mcp_servers"] = [{"type": "url", "name": "brightdata",
                                      "url": BRIGHTDATA_URL.format(token=token)}]
            kwargs["tools"] = [{"type": "mcp_toolset",
                                "mcp_server_name": "brightdata"}]
            resp = None
            # the connector runs the tool loop server-side; pause_turn means it
            # hit the server's iteration cap — re-send to resume, bounded by
            # the page budget
            for _ in range(max_pages + 3):
                resp = client.beta.messages.create(**kwargs)
                if resp.stop_reason != "pause_turn":
                    break
                kwargs["messages"] = kwargs["messages"] + [
                    {"role": "assistant", "content": resp.content}]
        else:
            resp = client.messages.create(**kwargs)
    except AgentApiError:
        raise
    except Exception as exc:
        raise AgentApiError(f"{type(exc).__name__}: {str(exc)[:300]}") from exc

    if resp is None or resp.stop_reason == "refusal":
        raise AgentApiError("the model declined or returned nothing")
    text = _text(resp)
    if not text:
        raise AgentApiError("the model returned no text")
    if schema:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise AgentApiError(f"invalid JSON despite schema: {exc}") from exc
    return text
