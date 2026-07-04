---
name: find-fullenrich
description: Use when the user wants to source a list of companies or contacts matching an ICP using FullEnrich search — e.g. "find me 50 Heads of Sales at French SaaS companies". Creates rows in the workspace database.
---

# Find via FullEnrich

Source companies and contacts with FullEnrich search (MCP) and write them to
the workspace database. You are a brick: you read criteria, you write rows,
you report a receipt. Read the contract in this plugin's BRICK.md.

## Steps

1. Verify you are in a workspace (`tools/db.py` exists). If not, tell the user
   to run workspace-init first, stop.
2. Build search filters from the user's request. If `context/icp.md` exists,
   use it to fill the gaps (industry, size, geography, titles). State the
   filters you are about to use in one line.
3. Preview (free): run the FullEnrich search, look at the first 10 results and
   the total count. Report: "~N matches. Export costs 0.25 credit per contact.
   Export how many?" — WAIT for user confirmation. Never export more than 100
   without an explicit override.
4. Export the confirmed volume. For each result, write to the database
   (never into the conversation):
   - company: `python3 tools/db.py upsert companies --key domain --set domain=<d> --set name=<n> --set source=fullenrich`
   - contact: `python3 tools/db.py insert people --set company_id=<id> --set first_name=<f> --set last_name=<l> --set title=<t> --set linkedin_url=<u> --set source=fullenrich`
   The upsert returns the company id to link the contact.
5. Receipt: "Added X companies, Y contacts (Z duplicates merged). Next:
   enrich-website for the pitch column, enrich-email for emails." Show at most
   3 sample names as illustration.

## Guardrails

- No rows in the conversation — receipts and up to 3 samples only.
- Any credit-consuming action requires prior announced volume + confirmation.
- Do not enrich here (no emails, no phones) — that is enrich-email's job.
