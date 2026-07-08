---
name: enrich-buying-committee
description: Find WHO to contact at each company — the decision-maker or the champion, chosen by strategy, not both. Use when the user says "trouve les décideurs", "qui contacter", "trouve le champion", "buying committee", "trouve les bons contacts". Creates contacts rows from a cost-ordered waterfall (registry → FullEnrich search → LinkedIn SERP → team page), one target per company.
---

# Enrich buying committee

**Before anything, read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`.**

Turns enriched companies into ONE right contact each. This skill is
strategic before it is mechanical: it decides WHO to hunt (champion vs
decision-maker) from the ICP and the offer, once per workspace — then
guarantees a verified answer per company through a cheap-first waterfall.

It reads what `/bricks:enrich-firmographics` wrote (`employees`,
`executives`, `parent_company`, `company_category`) — run it first on
rows that lack them; column relay, never a call. FullEnrich: useful but
not blocking — searches are free; if disconnected, the waterfall skips
that rung and says so.

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
  decision-maker: gérant|founder|CEO|directeur général; champion: the
  operational role your offer helps daily).
- **Fallback rule**: if the chosen type is unfindable after the full
  waterfall — `none` (strict) or `other_type` (take the other role,
  labeled). Default: none.

Present the plan in 5-6 lines, get explicit confirmation, persist it to
`<workspace>/context/targeting-plan.json`. Re-runs reuse it silently;
re-ask only if `context/` changed. One exception: when the user already
dictated the doctrine verbatim in `context/icp.md` ("Décideur type : le
gérant"), restate the plan and proceed without blocking — their context
IS the confirmation.

## Phase 1 — The waterfall, in waves (one rung × whole batch, cheap first, verified always)

Select companies with `committee_status` NULL or `pending`, skipping
disqualified rows. Run the rungs as WAVES across the whole batch, never
as per-company waterfalls: wave A on every company at once, wave B only
on A's unresolved companies, and so on — a company resolved in one wave
never enters the next. Within a wave, all calls fire IN PARALLEL in one
message; prefer the batch tool variant (`search_engine_batch`,
`scrape_batch`) when several companies need the same rung.
Stop-at-first-verified-hit still holds per company — it just happens
between waves:

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

**Write per wave** via `db.py` (§4, one batched write as each wave
completes): a `contacts` row per resolved company — `company_id` AND
`company_name` (denormalized on purpose: the table is read by humans, a
bare id is unreadable in the front), `full_name`, `role` (actual title),
`role_type` (`decision-maker` | `champion`), `linkedin_url` (when rung
C/B gives it), `source` (`registry` | `fullenrich-search` |
`linkedin-serp` | `team-page`), `status='new'` — then
`committee_status='done'`. One contact per company (the plan's type),
duplicates checked on (company_id + full_name).

## Volume mode

Up to ~40 companies, the main thread's parallel waves are the fast path
— no subagents (each one is a cold start). Beyond ~40: batches of 5-8
per subagent, up to 10 in parallel; subagents run rungs B-D as waves and
append candidates to `bricks/tmp/committee-<date>/candidates.jsonl`
(never touching the database); the main thread verifies and commits via
`db.py`. Announce SERP credit usage before launching (§7).

## Receipt

"Contacts: X via registry (free), Y via FullEnrich search (free), Z via
LinkedIn SERP (~Z credits), W via team pages. N not_found (fallback:
<rule>). Group-owned companies skipped registry: [names]." Max 3 sample
contacts. Next step as a statement: "Next: `/bricks:enrich` (emails) sur
les nouveaux contacts, puis `/bricks:write-outreach` — dis le mot."
