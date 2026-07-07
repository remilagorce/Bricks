---
name: find
description: Find companies and contacts matching an ICP and write them into the current Bricks workspace database. Use when the user wants to source leads, build a prospect list, "trouve des entreprises", "find companies", "build a list".
---

# Find — source companies & contacts

**Before anything, read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`** — the shared
contract every skill obeys (workspace, context gate, the only door, the iron
gate). The gates below are the find-specific application of it.

## Gates (before anything)

1. `python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/workspace.py" status` — if there is
   no current workspace, create one named after the search:
   `python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/workspace.py" new <slug>`.
2. Read `context/offer.md` and `context/icp.md` in the workspace. If the request
   contradicts them, STOP and ask (switch workspace, new workspace, or update
   the context).
3. If `icp.md` is still empty (TODO placeholders) or the request has no
   targeting criteria → invoke `/bricks:gtm-onboard` in a subagent before
   continuing. Do not source leads until the ICP exists. If the gate has
   targeting criteria but nothing in `icp.md`, complete `icp.md` with the
   inferred ICP.

## Workflow

1. **Target** — make the criteria explicit (industry, geography, size...);
   default to what `icp.md` says. Default is for company but people if explicitly mentionned. 
2. **Source**, in this order:
   - **FullEnrich MCP** (`mcp__fullenrich__*` tools) for firmographic segments:
     `search_companies` as a preview (10 results + total), always print the preview and format it to the user as a table with all the information from the MCP. Also print the the request term in a human comprehensible natural language. Confirm the volume and the preview before the next part.
     with the user, then `export_companies` → download the CSV → import:
     `python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" import-csv companies <file.csv> --key domain`
     If the MCP tools are missing, say it once (`/mcp` → fullenrich) and fall back.
   - todo : Alternative methode in skills (write the skills)
3. **Write** — save the sourced rows to a temp CSV, then import with the file
   as a positional argument (never raw SQL, never fabricated data, never mass
   JSON in the conversation):
   `python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" import-csv companies <file.csv> --key domain`
   Standard columns — companies: `name`, `domain`, `source`; contacts:
   `company_id`, `full_name`, `role`, `email`, `linkedin_url`, `source`.
4. **Receipt** — tell the user how many were found / skipped as duplicates,
   show at most 3 sample rows. The mass lives in the database, never in the
   conversation.
