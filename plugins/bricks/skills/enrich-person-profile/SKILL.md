---
name: enrich-person-profile
description: Complete existing contacts with verified role, seniority and LinkedIn URL. Use when the user says "complète les profils", "trouve leurs LinkedIn", "c'est quoi leurs postes", "enrichis mes contacts", "person profile". Free-first waterfall (FullEnrich search → LinkedIn SERP → team page) for contacts that arrived without identity columns (CRM import, CSV, manual adds) — never guesses, never logs into LinkedIn.
---

# Enrich person profile

**Before anything, read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`.**

Completes KNOWN people. `/bricks:enrich-buying-committee` decides WHO to
hunt at a company; this brick takes contacts that already exist (CRM
import, CSV, dictated lists, old rows) and fills the identity columns
that `/bricks:write-outreach`, scoring and `/bricks:signal-person` need:
`role`, `seniority`, `linkedin_url`. Every value is verified in its
source or the row is `not_found` — never a guess.

IN relay: each contact needs `full_name` + a resolvable company
(`company_name`, or `company_id` → the companies row; a company `domain`
sharpens rung A — run `/bricks:enrich-firmographics` first when it is
missing). No contacts at all → that is `/bricks:enrich-buying-committee`'s
job; point the user there. FullEnrich: not blocking — searches are free;
if disconnected, rung A is skipped and the receipt says so.

## The waterfall, in waves (one rung × whole batch, cheap first, stop at first VERIFIED hit)

Select contacts with `profile_status` NULL or `pending` whose company is
not disqualified. Rows with `left_company=1` (`/bricks:signal-person`'s
verdict: the person moved to another company) are out of scope — their
identity columns describe who the person was at THIS company and stay
frozen. Execution is by WAVES, never per contact: rung A fires for ALL
contacts in scope in one parallel message (or one batch call), rung B
only for A's misses, rung C for B's misses — a contact verified in one
wave never enters the next. Stop-at-first-hit holds per contact, between
waves.

**Budget once, up front (§7)**: count the rows that could reach rungs
B/C ("up to N contacts × 2 SERP queries → max ~2N credits"), flag the
low-prior rows (see rung B). Free-only runs need no confirmation —
announce and proceed; real credit spend gets ONE confirmation for the
whole batch, then never re-ask per contact. Chain GO: when this brick
runs as a step the user already authorized in a multi-brick plan, its
budget line was announced there — do not re-ask. The receipt ends with
statements, never questions.

- **A. FullEnrich people search (free — searches cost 0 credits)** —
  search `person_names` = full_name + `current_company_domains` (or
  company names). If the row already carries a `linkedin_url`, search by
  `person_linkedin_urls` instead (exact, strongest key). Accept only
  when the CURRENT employment matches our company AND the name matches —
  note that search results may mask last names ("Hakim A."): first name
  + last initial must match our full_name. Take: current title →
  `role`, seniority → `seniority`, professional network URL →
  `linkedin_url`.
- **B. LinkedIn via SERP (Bright Data `search_engine`, ~1 credit, 2
  queries max)** — `site:linkedin.com/in "<full name>" "<company>"` in
  the company's language. Read the INDEXED SNIPPET only — never
  logged-in pages; `scrape_as_markdown` on a `/in/` profile hits the
  login wall (confirmed by Bright Data), do not attempt it. Accept when
  the snippet shows the person CURRENTLY in that role at that company.
  **Low-presence prior (field-tested)**: when the company has no domain
  AND is tiny or an artisan trade (≤ ~10 employees, local trade NAF),
  the LinkedIn hit rate is near zero — a field run spent 6 credits on
  SERP for 0 hits on exactly such rows. For those rows rung B is
  OPT-IN: name them in the upfront announcement ("N rows are low-prior —
  skip B and derive seniority from the registry title, or spend
  anyway?") and default to skipping.
- **C. Team/about page or press bio (Bright Data scrape, ~1 credit)** —
  scrape the company site's team page or a press release naming the
  person; best exact-name match only.
- **Optional precision rung** — `web_data_linkedin_person_profile`
  (Bright Data pro tools): when a `linkedin_url` is known but
  role/seniority still missing after A, one structured record fills
  both. Per-record cost — announce at volume (§7). Tool absent from the
  tool list → skip silently.

**Verification rule (all rungs)**: name + role + company must cohere in
the source itself. Ambiguity → next rung. Nothing after C →
`profile_status='not_found'`. This rule has PRIMACY over any relay or
refresh request: if the source shows the person currently at a DIFFERENT
company than the row's, never write that title onto the row —
field-tested failure (a job-change relay wrote a Doctrine title on a
Predictice-anchored contact). Report the mismatch (that is
`/bricks:signal-person`'s `job_change` territory) and close the row
`not_found`.

**Seniority — French legal titles override provider labels**: a gérant /
président / PDG / DG / founder who IS the company's registry executive
is the decision-maker — write `C-Level`, whatever the provider labeled
them (field-tested: "Gérant" came back as "Manager", which would mislead
scoring and sequence tone downstream). Otherwise rung A keeps
FullEnrich's value verbatim; other rungs derive conservatively from the
title (C-level / VP / Head / Director / Manager / Senior / Entry) — when
the title does not say, leave `seniority` empty rather than guess.

**Write per wave** via `db.py` (§4, one batched write as each wave
completes), per contact: `role`, `seniority`, `linkedin_url`,
`profile_source` (`fullenrich-search` | `linkedin-serp` | `team-page` |
`linkedin-record`), then `profile_status='done'`. Never overwrite a
non-empty `role`/`linkedin_url` with a weaker-rung value.

**Never create rows**: this brick fills columns on existing contacts —
people discovered along the way (a co-gérant, a better-fitting
operational champion) are SUGGESTED in the receipt, never inserted;
adding people is `/bricks:enrich-buying-committee`'s job.

## Volume mode

Up to ~40 contacts, the main thread's parallel waves are the fast path —
no subagents. Beyond ~40: batches of 5-8 per subagent, up to 10 in
parallel; subagents run rungs A-C as waves and append candidates to
`bricks/tmp/profile-<date>/candidates.jsonl` (never touching the
database); the main thread verifies and commits via `db.py`. The single
upfront budget announcement covers the whole run — subagents never spend
beyond it.

## Receipt

"Profiles: X via FullEnrich search (free), Y via LinkedIn SERP (~Y
credits), Z via team/press pages. N not_found." Max 3 sample rows. Next
steps as statements: `/bricks:enrich` (emails) → `/bricks:write-outreach`;
`/bricks:signal-person` can now watch the new `linkedin_url` rows.
