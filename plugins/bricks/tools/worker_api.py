#!/usr/bin/env python3
"""Lightweight per-row worker — replaces `claude -p` to kill the CLI cold-start.

The engine's default worker boots a full Claude Code CLI (Node + MCP handshake
+ auth) for EVERY row (researcher.py). Across hundreds of rows that fixed
cold-start dominates. worker_api.py is a drop-in BRICKS_WORKER_CMD override
that talks to the Anthropic Messages API directly: one lean Python process per
row, no CLI boot, structured JSON out. For the web lane it uses the API's
remote MCP connector so Bright Data still drives the navigation server-side —
no per-row MCP re-handshake.

Contract (CONVENTIONS §11): reads the fully-built worker prompt on stdin
(researcher.build_worker_prompt already injected the mission, rules and the
JSON response format), prints the answer JSON on stdout, exits 0. On failure
exits 1 with a short reason on stderr — researcher.py turns that into a failed
row and retries once.

Enable it (per workspace, once):
    export BRICKS_WORKER_CMD="python3 /abs/path/plugins/bricks/tools/worker_api.py"

Context is passed automatically by researcher.py via env:
    BRICKS_WORKER_MODEL     haiku|sonnet|opus or a full model id (default haiku)
    BRICKS_WORKER_TOOLS     none|web
    BRICKS_WORKER_MAX_PAGES web page budget (bounds the MCP tool loop)
    ANTHROPIC_API_KEY       (or an auth token) — loaded from ~/.bricks/env
    BRIGHTDATA_API_TOKEN    only for --tools web

Billing note: this runs on the Anthropic API (API credits), NOT the Claude
subscription that `claude -p` uses — that is the trade for removing the cold
start. Leaving BRICKS_WORKER_CMD unset keeps the subscription path unchanged.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envfile  # noqa: E402

envfile.load()  # ~/.bricks/env → ANTHROPIC_API_KEY / BRIGHTDATA_API_TOKEN

# CLI aliases (what runner.py passes) → Messages API model ids.
MODEL_ALIASES = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-4-8",
}
DEFAULT_MODEL = "claude-haiku-4-5"
BRIGHTDATA_URL = "https://mcp.brightdata.com/mcp?token={token}&pro=1"
MCP_BETA = "mcp-client-2025-11-20"


def die(reason: str) -> int:
    print(reason[:300], file=sys.stderr)
    return 1


def resolve_model(raw: str | None) -> str:
    raw = (raw or "").strip()
    if not raw:
        return DEFAULT_MODEL
    return MODEL_ALIASES.get(raw, raw)


def answer_text(resp) -> str:
    return "".join(b.text for b in resp.content
                   if getattr(b, "type", None) == "text").strip()


def run_plain(client, model: str, prompt: str) -> str:
    resp = client.messages.create(
        model=model, max_tokens=1024,
        messages=[{"role": "user", "content": prompt}])
    return answer_text(resp)


def run_web(client, model: str, prompt: str, max_pages: int) -> str:
    token = os.environ.get("BRIGHTDATA_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("--tools web needs BRIGHTDATA_API_TOKEN in the env")
    mcp_servers = [{"type": "url", "name": "brightdata",
                    "url": BRIGHTDATA_URL.format(token=token)}]
    tools = [{"type": "mcp_toolset", "mcp_server_name": "brightdata"}]
    messages = [{"role": "user", "content": prompt}]
    resp = None
    # The connector runs the tool loop server-side; pause_turn means it hit the
    # server's iteration cap — re-send to resume, bounded by the page budget.
    for _ in range(max_pages + 3):
        resp = client.beta.messages.create(
            model=model, max_tokens=2048, betas=[MCP_BETA],
            mcp_servers=mcp_servers, tools=tools, messages=messages)
        if resp.stop_reason != "pause_turn":
            return answer_text(resp)
        messages.append({"role": "assistant", "content": resp.content})
    return answer_text(resp) if resp else ""


def main() -> int:
    prompt = sys.stdin.read()
    if not prompt.strip():
        return die("worker_api: empty prompt on stdin")
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return die("worker_api needs the anthropic SDK: pip install anthropic")

    model = resolve_model(os.environ.get("BRICKS_WORKER_MODEL"))
    tools = (os.environ.get("BRICKS_WORKER_TOOLS") or "none").strip()
    try:
        max_pages = int(os.environ.get("BRICKS_WORKER_MAX_PAGES") or "5")
    except ValueError:
        max_pages = 5

    client = anthropic.Anthropic()  # resolves ANTHROPIC_API_KEY / auth token
    try:
        text = (run_web(client, model, prompt, max_pages) if tools == "web"
                else run_plain(client, model, prompt))
    except Exception as exc:  # any API/parse failure → failed row + retry
        return die(f"worker_api {type(exc).__name__}: {exc}")
    if not text:
        return die("worker_api: model returned no text")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
