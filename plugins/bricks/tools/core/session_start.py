#!/usr/bin/env python3
"""SessionStart hook — injects the current workspace context into the session.

Whatever this prints on stdout lands in the session context. It must NEVER
break a session: any exception -> a short hint, exit 0.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import workspace as ws


def main() -> int:
    try:
        import workspace
        # Report state only — never create anything here. Bricks stores GTM data
        # in a ./bricks/ folder in the working directory; creating it eagerly on
        # every session would litter unrelated directories. Initialization is
        # LAZY: the workspace skill creates the root + workspace on the first GTM
        # action, in the right place. This hook just tells Claude where things
        # stand so it can act (or set up) when the user actually asks.
        st = workspace.status()
        lines = ["[bricks] Session context:"]

        if not st.get("initialized"):
            lines.append("- Bricks is not initialized in this directory (no bricks/ "
                         "yet). Nothing is created until you act. When the user asks "
                         "for GTM work, /bricks:workspace sets it up here.")
        elif not st.get("current"):
            lines.append("- No current workspace. Run /bricks:workspace to create one "
                         "(new <name>), or asking for GTM work will create one.")
        else:
            name = st["current"]
            lines.append("- Current workspace below. Show this banner to the user "
                         "VERBATIM inside a fenced code block before your first reply:")
            lines.append(ws.banner(name))
            lines.append(f"- Tables: {', '.join(st.get('tables') or []) or 'none yet'}")
            lines.append(f"- Context files: {', '.join(st.get('context') or []) or 'none'}")
            icp = os.path.join(st.get("path", ""), "context", "icp.md")
            if os.path.isfile(icp):
                with open(icp, encoding="utf-8") as f:
                    head = [ln.strip() for ln in f if ln.strip()][:5]
                if head:
                    lines.append("- ICP summary: " + " / ".join(head))
        lines.append("- Read context/offer.md and context/icp.md before any sourcing "
                     "or enrichment; STOP if the request contradicts them.")
        lines.append("- Before enriching, check that mcp__fullenrich__* tools are "
                     "connected (/mcp otherwise). Never fabricate enrichment data.")
        print("\n".join(lines))
    except Exception as exc:  # a hook must never break the session
        print(f"[bricks] hook error (ignored): {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
