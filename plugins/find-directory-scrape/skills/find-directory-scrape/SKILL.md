---
name: find-directory-scrape
description: Use when the user wants to source companies from an online directory, exhibitor list, curated listicle, or ranking page — e.g. "scrape les exposants de ce salon" or "récupère les boutiques de cet article". Uses Bright Data (JS rendering + anti-bot handled), writes company rows to the workspace database.
---

# Find via directory scraping (Bright Data)

Turn any listing page into company rows. You are a brick: you read a
directory, you write rows, you report a receipt. Scraping robustness is
delegated to Bright Data — never hand-roll fetching if its tools are
available. Contract in this plugin's BRICK.md.

## Setup check (once per workspace)

1. Verify you are in a workspace (`tools/db.py` exists), else point the user
   to workspace-init and stop.
2. Verify the Bright Data MCP tools are available (`scrape_as_markdown`…).
   If not: the workspace `.mcp.json` needs the hosted server —
   `https://mcp.brightdata.com/mcp?token=<API_TOKEN>` — and the user gets a
   free token at brightdata.com (5,000 requests/month, no credit card).
   Guide them, remind them to restart the session, and stop. If the user
   cannot set it up now, offer the degraded fallback: built-in WebFetch,
   static pages only — their call.

## Steps

1. Input: a directory URL. If the user only describes it ("les exposants de
   Maison&Objet"), use `search_engine` to locate the listing and confirm the
   URL with the user before scraping.
2. Scout: `scrape_as_markdown` on page 1. From the markdown, identify:
   - the repeating entry pattern (company name + link),
   - whether entry links go to external company sites or to internal detail
     pages of the directory,
   - pagination (next-page links, page count).
3. Announce the plan and WAIT only if it exceeds caps: "~N entries per page,
   M pages detected, ~M credits. I'll scrape up to 10 pages / 200 entries" —
   beyond those caps, ask before continuing.
4. Extract and write page by page, as you go:
   - entry with an external site link: normalize to a bare domain, then
     `python3 tools/db.py upsert companies --key domain --set domain=<d> --set name=<n> --set "source=directory:<host>"`
   - entry without an external link: check by name first
     (`select companies --where "name='<n>'"`), insert with no domain only if
     absent; count these separately.
   Never invent a domain from a company name.
5. If more than 3 pages: delegate batches of pages to subagents (Task tool,
   general-purpose). Each subagent scrapes its pages with `scrape_as_markdown`,
   writes rows via db.py itself, and returns ONLY counts. Scraped markdown
   never enters the main conversation.
6. Optional second pass — propose it, do not force it:
   - internal detail pages holding the websites: `scrape_batch` them in
     batches of 10 (announce the extra credits) and update the rows;
   - or entries still domain-less: `search_engine` per name (announce count).
7. Receipt: "Added X companies (Y with domain, Z without), W duplicates
   merged, P pages scraped (~P credits). Skipped pages: [list or none].
   Next: enrich-website on the new rows." Maximum 3 sample names.

## Guardrails

- Hard cap without explicit user override: 10 pages / 200 entries per run.
- Announce credit usage before scraping and in the receipt.
- Receipts only in the conversation — no row dumps, no page content.
- Re-runs are safe: domain upserts merge, name checks prevent domain-less
  duplicates.
