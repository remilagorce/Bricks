---
name: scan-mentions
description: Use when the user asks a specific question about a company's website — "est-ce qu'ils ont des clients dans la banque ?", "quel est leur stack ?", "est-ce qu'ils recrutent des sales ?". Takes the user's question as input, scans the site for matching mentions with Bright Data (JS rendering + anti-bot handled), and answers directly in the conversation in a short paragraph backed by evidence.
---

# Scan a website to answer one question (Bright Data)

The user asks a question about a company's site; you scan the pages likely
to hold the answer and reply directly in the conversation — a short
paragraph, not a file, not a report. The answer IS the deliverable.
Scraping robustness is delegated to Bright Data — never hand-roll fetching
if its tools are available.

## Input

Two things, both from the user's request:

1. **The site** — a domain or URL. If the user only gives a company name,
   use `search_engine` to find the official site and confirm it before
   scraping.
2. **The question** — what they want to know: named customers, partners,
   tech stack, hiring, pricing, funding, a specific keyword… If the request
   is too vague to scan for ("regarde ce site"), ask what they are looking
   for before spending any credit.

## Setup check

Verify the Bright Data MCP tools are available (`scrape_as_markdown`…).
If not: the MCP config needs the hosted server —
`https://mcp.brightdata.com/mcp?token=<API_TOKEN>` — and the user gets a
free token at brightdata.com (5,000 requests/month, no credit card).
Guide them, remind them to restart the session, and stop. If the user
cannot set it up now, offer the degraded fallback: built-in WebFetch,
static pages only — their call.

## Steps

1. Scout: `scrape_as_markdown` on the homepage. From the markdown and nav
   links, shortlist ONLY the pages relevant to the question — e.g. customers
   or case studies for a clients question, careers for hiring, pricing for
   pricing, docs/footer for tech stack, blog/press for news. 3–6 pages is
   the norm; the question drives the shortlist, not a fixed checklist.
2. Scrape the shortlist (`scrape_batch` in batches when available, otherwise
   page by page). Stop as soon as the question is answered — do not scrape
   the remaining pages just because they were shortlisted.
3. Extract what answers the question: the exact wording from the page, not
   a paraphrase, with the page it came from.
4. Answer directly in the conversation, nothing else — a short paragraph
   (3–6 sentences, no headers, no bullet list, no categories): open with a
   direct answer to the question, weave in the evidence that supports it
   (what the page actually says, and which page), and close with the cost
   ("P pages scraped, ~P credits"). E.g. "Oui — Acme cite BNP Paribas et
   Société Générale parmi ses clients sur la page /customers ('trusted by
   BNP Paribas, Société Générale...'), et met aussi en avant un partenariat
   avec Salesforce sur /partners. 4 pages scrapées (~4 crédits)."
   If the site does not answer the question, say so plainly in the same
   paragraph — "not found on the site" is a valid answer, never fill the
   gap with a guess.

## Guardrails

- Hard cap without explicit user override: 10 pages per question.
- The question bounds the scan: do not collect mentions the user did not
  ask about, do not turn this into a full-site audit.
- Evidence or it didn't happen: the answer must be traceable to what a page
  actually says. Never infer what the pages don't say.
- Page empty or blocked after one retry: skip it, continue; mention skipped
  pages only if they were likely to hold the answer.
- No files written, no raw page content in the conversation, no report
  structure (no headers, no per-category sections, no bullet dump) — one
  short paragraph, evidence woven in, the cost line at the end. That's the
  whole output.
