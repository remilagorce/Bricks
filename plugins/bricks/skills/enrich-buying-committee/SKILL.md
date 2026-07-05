---
name: enrich-buying-committee
description: Find WHO to contact at each company — the decision-maker or the champion, chosen by strategy, not both. Use when the user says "trouve les décideurs", "qui contacter", "trouve le champion", "buying committee", "trouve les bons contacts". Creates contacts rows from a cost-ordered waterfall (registry → FullEnrich search → LinkedIn SERP → team page), one target per company.
---

# Enrich buying committee

Turns enriched companies into ONE right contact each. This skill is
strategic before it is mechanical: it decides WHO to hunt (champion vs
decision-maker) from the ICP and the offer, once per workspace — then
guarantees a verified answer per company through a cheap-first waterfall.
Contract in this directory's BRICK.md.

## Before anything

Follow `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` §2 and §3. This skill reads
what enrich-firmographics wrote (`employees`, `executives`,
`parent_company`, `company_category`) — run it first on rows that lack
them; column relay, never a call. FullEnrich (§4): useful but not
blocking — searches are free; if disconnected, the waterfall skips that
rung and says so.

## Phase 0 — The targeting plan (once per workspace, user-confirmed)

Read `context/offer.md`, `context/icp.md` (Buying roles section) and
`context/personas/`. Derive and present ONE plan:

- **Per size bucket, the target type** — the default doctrine:
  - small companies (≲ 20 employees): no real champion exists — target
    the DECISION-MAKER (founder/gérant/CEO);
  - mid-size: decision-maker of the buying function (title patterns from
    the ICP, e.g. head of purchasing, head of sales);
  - large companies AND an expensive/complex offer: CHAMPION first — the
    operational believer who sells internally (the personas say who).
- **Title patterns per target type**, in the company's language (e.g.
  decision-maker: gérant|founder|CEO|directeur général; champion:
  the operational role your offer helps daily).
- **Fallback rule**: if the chosen type is unfindable after the full
  waterfall — `none` (strict) or `other_type` (take the other role,
  labeled). Default: none.

Present the plan in 5-6 lines, get explicit confirmation, write it to
`memory/state.json` (`targeting_plan`) and one line in `NOTES.md`.
Re-runs reuse it silently; re-ask only if context/ changed.

## Phase 1 — The waterfall, per company (cheap first, verified always)

Select companies with `committee_status='pending'` (init the column on
rows in scope, claim `running` via `db-writer` — absolute db path). For
each, stop at the FIRST rung that yields a VERIFIED person:

- **A. Registry relay (free, instant)** — only when the target type is
  decision-maker AND the company is small: take the human in
  `executives` (role Gérant/Président, `entity` ≠ true). A corporate
  officer (`parent_company` set) is NOT a contact — skip to B and note
  the group.
- **B. FullEnrich people search (free — searches cost no credits)** —
  search by title patterns + company domain, seniority filters. Take a
  result only if the current company matches.
- **C. LinkedIn via SERP (Bright Data `search_engine`, ~1 credit/query)**
  — query `site:linkedin.com/in "<title pattern>" "<company>"` in the
  company's language. Read the INDEXED SNIPPET only (never log into
  LinkedIn): accept when the snippet shows the person CURRENTLY in that
  role at that company. 2 queries max per company.
- **D. Team page (Bright Data scrape, ~1 credit)** — scrape the site's
  team/about page and pick the best title match.

**Verification rule (all rungs)**: name + role + company must cohere in
the source itself. Ambiguity → next rung. Nothing after D → the fallback
rule from the plan, else `committee_status='not_found'`. NEVER invent a
person, never write an unverified one.

**Write immediately** per company via `db-writer`: a `contacts` row —
`company_id`, `full_name`, `role` (actual title), `role_type`
(`decision-maker` | `champion`), `linkedin_url` (when rung C/B gives it),
`source` (`registry` | `fullenrich-search` | `linkedin-serp` |
`team-page`), `status='new'` — then `committee_status='done'`. One
contact per company (the plan's type), duplicates checked on
(company_id + full_name).

## Volume mode

More than 10 companies: batches of 5-8 per subagent, up to 10 in
parallel; subagents run rungs B-D and append candidates to
`staging/committee-<date>/candidates.jsonl` (never touching the
database); the main thread verifies and commits via `db-writer`.
Announce SERP credit usage before launching (money gate §8).

## Close the run

`memory/state.json` (counts per rung), one `NOTES.md` line, receipt:
"Contacts: X via registry (free), Y via FullEnrich search (free), Z via
LinkedIn SERP (~Z credits), W via team pages. N not_found (fallback:
<rule>). Group-owned companies skipped registry: [names]." Max 3 sample
contacts. Next step: enrich (emails) on the new contacts, then
write-sequence.
