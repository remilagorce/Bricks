---
name: enrich-website
description: Use when the user wants to enrich companies from their websites — extracting what each company does (pitch), site language, and a size hint. Works on rows where website_status is pending.
---

# Enrich from website

Visit each company's site and write three columns: `pitch`, `language`,
`size_hint`. You are a brick: select pending rows, work in batches, write
results immediately, report a receipt. Contract in this plugin's BRICK.md.

## Steps

1. Select the work list:
   `python3 tools/db.py select companies --where "website_status='pending' AND status!='disqualified' AND domain IS NOT NULL" --cols id,domain --limit 50`
   Honor any narrower scope the user asked for. Report only the count.
2. Rows without a domain: mark `website_status='not_found'` directly.
3. Mark the batch as claimed BEFORE working:
   `python3 tools/db.py write companies <id> --set website_status=running` (per row).
4. Work in batches of 5. If more than 5 rows, delegate each batch to a
   subagent (Task tool, general-purpose) with this exact mission:
   - For each {id, domain}: fetch `https://<domain>` (follow to /about or
     /contact if the homepage is thin). Extract: pitch = ONE sentence, what
     they do and for whom, in the site's own language; language = ISO code;
     size_hint = solo | small | mid | large (team page, tone, footprint).
   - Write each result immediately:
     `python3 tools/db.py write companies <id> --set pitch=<p> --set language=<l> --set size_hint=<s> --set website_status=done`
   - Unreachable after one retry: `--set website_status=failed`. No site:
     `--set website_status=not_found`.
   - Return ONLY counts: done / not_found / failed. Never return page content.
   If 5 rows or fewer, do the same inline with WebFetch.
5. Receipt: "Websites: X done, Y not_found, Z failed (re-run to retry failed)."
6. If `context/icp.md` has kill rules that map to these columns (e.g. language
   or size), flag how many rows now match a kill rule — but do NOT disqualify
   here; that is a scoring brick's job.

## Guardrails

- Never dump page content or full rows into the conversation.
- Never batch-write at the end — one write per row, as results arrive.
- Re-runs must only pick up `pending` and `failed` rows (idempotence).
