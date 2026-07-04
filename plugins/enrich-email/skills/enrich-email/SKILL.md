---
name: enrich-email
description: Use when the user wants to find professional email addresses for contacts in the workspace database, via FullEnrich waterfall enrichment. Paid per contact — always confirms volume first. Works on rows where email_status is pending.
---

# Enrich emails via FullEnrich

Find verified professional emails for pending contacts and write them to the
database. You are a brick, and a PAID one: nothing gets enriched without an
announced volume and explicit user confirmation. Contract in BRICK.md.

## Steps

1. Select the work list (note the joins are done by selecting twice):
   `python3 tools/db.py select people --where "email_status='pending' AND status!='disqualified'" --cols id,first_name,last_name,linkedin_url,company_id --limit 50`
   Then fetch the domains of the involved companies:
   `python3 tools/db.py select companies --where "status!='disqualified'" --cols id,domain`
   Keep only contacts with (first_name AND last_name) AND (domain OR
   linkedin_url). Contacts missing both identifiers: mark
   `email_status='not_found'` immediately — never guess, never spend.
2. Announce: "N contacts ready for email enrichment. This is PAID (FullEnrich
   credits, debited per contact). Proceed with how many?" — WAIT for explicit
   confirmation. Hard cap 50 per run unless the user explicitly overrides.
3. Mark the confirmed rows `email_status='running'`.
4. Enrich in batches of 10 via the FullEnrich MCP enrichment tools, passing
   first name, last name, and company domain (or LinkedIn URL). As each
   result arrives, write it immediately:
   - found: `python3 tools/db.py write people <id> --set email=<e> --set email_status=done`
   - nothing found: `--set email_status=not_found`
   - error: `--set email_status=failed` (continue the batch)
5. Receipt: "Emails: X found, Y not_found, Z failed. Credits spent on X+Y
   lookups. Next: write-sequence for the X contacts with an email."

## Guardrails

- Never print email addresses in bulk in the conversation — counts only.
- Never enrich a contact whose row or parent company is disqualified.
- MCP not connected → tell the user to run `/mcp` and authenticate, stop.
- Re-runs only pick `pending` and `failed` rows (idempotence).
