#!/usr/bin/env python3
"""SessionStart hook — injects Bricks context at the start of every session.

Whatever this prints on stdout is added to Claude's context, so every
session opens already knowing:
1. The current workspace (name, goal, tables) — no file reading needed.
2. That the FullEnrich MCP connection must be verified up front.

This hook must never break a session: any error degrades to a hint and the
exit code is always 0.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import workspace as ws  # noqa: E402


def main() -> int:
    lines = ["[bricks] Session context:"]
    try:
        status = ws.status("bricks")
        if not status.get("initialized"):
            lines.append(
                "- Workspace: Bricks is not initialized in this directory. If the "
                "user asks for GTM work, /bricks:workspace auto-initializes it."
            )
        elif not status.get("currentWorkspace"):
            lines.append(
                "- Workspace: initialized but no current workspace — create one "
                "with /bricks:workspace new <name>."
            )
        else:
            name = status["currentWorkspace"]
            current = status.get("current") or {}
            goal = f" — goal: {current['goal']}" if current.get("goal") else ""
            tables = current.get("tables") or []
            context = current.get("context") or []
            lines.append(f"- Current workspace: {name}{goal}")
            lines.append(f"- Tables: {', '.join(tables) if tables else 'none yet'}")
            lines.append(
                f"- Context files: {', '.join(context) if context else 'none'} — "
                "read context/offer.md and context/icp.md before any sourcing, "
                "enrichment or writing work. If the user's request contradicts "
                "them (another product, another ICP), STOP and ask whether to "
                "switch workspace, create a new one, or update the context."
            )
            if status.get("warning"):
                lines.append(f"- Warning: {status['warning']}")
            lines.append(
                "- MANDATORY GREETING: open your VERY FIRST reply of this session "
                "with the banner below, verbatim, inside a fenced code block, "
                "immediately followed by the line: "
                f"« Bienvenue, tu es actuellement sur le workspace **{name}** » "
                "— then answer the user. Show the same banner again after every "
                "workspace switch or creation (new/switch return it as `banner`)."
            )
            lines.append("--- banner start ---")
            lines.append(ws.banner(name))
            lines.append("--- banner end ---")
    except Exception as exc:  # never block the session
        lines.append(f"- Workspace status unavailable ({exc})")

    lines.append(
        "- FullEnrich MCP: Bricks enrichment relies on the 'fullenrich' MCP server "
        "bundled with this plugin. Check NOW whether mcp__fullenrich__* tools are "
        "available in your tool list. If they are NOT, the user is not signed in: "
        "tell them at the first opportunity to run /mcp, pick 'fullenrich' and sign "
        "in with their FullEnrich account in the browser. Enrichment work must not "
        "start until this is done, and enrichment data must never be fabricated as "
        "a fallback."
    )
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())