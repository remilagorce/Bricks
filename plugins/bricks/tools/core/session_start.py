#!/usr/bin/env python3
"""SessionStart hook — injects the current workspace context into the session.

Whatever this prints on stdout lands in the session context. It must NEVER
break a session: any exception -> a short hint, exit 0.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    try:
        import workspace
        st = workspace.status()
        lines = ["[bricks] Session context:"]
        if not st.get("current"):
            lines.append("- No current workspace. If the user asks for GTM work, "
                         "create one first: workspace.py new <name>.")
        else:
            lines.append(f"- Workspace: {st['current']} (db: {st.get('db')})")
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
