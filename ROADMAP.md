# Bricks — roadmap

The reference plan for the team. Architecture rules live in
`plugins/bricks/CONVENTIONS.md`; per-skill contracts in each skill's
`BRICK.md`. This file says where we are going, how we work today, who owns
what, and the IN → OUT contract + strategy of every block, shipped or not.

---

## 1. Final architecture (the target product)

Bricks is the open-source GTM engine: a Clay alternative where the user owns
the data (one local SQLite per workspace) and the intelligence (their own
Claude subscription). Nobody resells credits or tokens.

```
┌─ COCKPIT (local app, V2) ──────────────────────────────────────┐
│  tabs = workspaces · Clay-style live table · chat panel        │
│  draft→approved validation queue · spawns headless sessions    │
├─ ORCHESTRATION ────────────────────────────────────────────────┤
│  natural language turn-by-turn (auto delegation)               │
│  + playbooks for repeatable motions (explicit dispatch)        │
├─ SKILLS = BRICKS (one capability each) ────────────────────────┤
│  find · enrich · transform · write · score · crm · signal …    │
├─ PLUMBING (the frozen contract) ───────────────────────────────┤
│  workspace.py (multi-workspace lifecycle, staging, memory)     │
│  db.py (dynamic Clay-style tables) · db-writer (single door)   │
│  hooks (session banner, send-guard) · front (web UI)           │
├─ WORKSPACES (physical context isolation) ──────────────────────┤
│  1 workspace = 1 client = 1 sealed world under bricks/         │
│  context/ (offer, icp, personas) · bricks.db · staging/ memory/│
└─ DISTRIBUTION ─────────────────────────────────────────────────┘
   claude plugin marketplace add remilagorce/Bricks
   MkDocs site for humans · community bricks later
```

Iron rules at every layer: data flows through the database, never the
conversation (receipts only) · paid actions announce volume + cost and wait
for explicit confirmation (CONVENTIONS §8) · nothing leaves the machine
without a human (`draft → approved` is a human act) · context drift stops
the run (§3).

## 2. The star architecture (how we develop today)

Everything is one plugin (`plugins/bricks`) but internally we build in a
star: **bricks never call each other — the workspace database is the bus.**

- One capability = one skill directory + its `BRICK.md` contract (§9).
- A brick's IN and OUT are columns + statuses. Brick-to-brick handoff is a
  WHERE clause (`enrich` picks up what `find` wrote via
  `X_status='pending'`), never a call.
- All database access goes through the `db-writer` agent (Rule 2 in
  CLAUDE.md), always with the absolute `bricks.db` path.
- Statuses make everything idempotent and resumable: `pending → running →
  done | not_found | failed`; row-level `new | disqualified`; messages
  `draft → approved → sent`.

Why it eases dev: one brick = one skill dir = one branch = one PR = one
person. Two people never touch the same files; the only shared surface is
the plumbing + CONVENTIONS (changes there = PR approved by both Rémi and
Robin). Playbooks compose bricks by *runtime discovery* — a brick shipped
next week automatically joins existing motions.

## 3. Status and split

### Shipped ✅

| Block | Owner | State |
|---|---|---|
| Plumbing: workspace.py, db.py (dynamic), db-writer, session hook, front | Rémi | ✅ shipped, smoke-tested |
| CONVENTIONS §1-7 (workspace, drift, gates, statuses, staging, memory) | Rémi | ✅ shipped |
| CONVENTIONS §8 money gate + §9 BRICK contracts | Robin | ✅ shipped |
| workspace / interface / find / enrich / transform / scan-mentions | Rémi | ✅ shipped (find + enrich patched after test #1) |
| find-directory-scrape / find-lookalike / write-sequence / playbook-lookalike | Robin | ✅ shipped |
| enrich-firmographics (+ tools/firmo.py, official gov API) | Robin | ✅ shipped, field-tested ×2 |
| enrich-buying-committee (targeting plan + waterfall) | Robin | ✅ shipped, field-tested |
| enrich-person-profile (identity waterfall, FullEnrich-search first) | Robin | ✅ shipped, field-tested ×1 (0.4.1 patches) |
| signal-person (job change / hiring / posts / news scan) | Robin | ✅ shipped, field-tested ×1 (0.4.2 patches) |
| Bright Data + FullEnrich MCP wiring | Robin | ✅ shipped, both Connected |

### Field-test log — the loop that improves the product

Every fix below came from a real desktop test session. Plugin version at
head: **0.4.2**.

| Version | Trigger | What changed |
|---|---|---|
| 0.2.0 | stale-cache discovery (two sessions ran the pre-merge plugin) | CLAUDE.md Rule 3: version bump on every plugin change; merged plugin actually live |
| 0.2.1 | tech-startups run #1 | `parent_company` (holding detection, e.g. Predictice → FORSETI/Doctrine), siren-direct lookup, trade-name retry |
| 0.2.2 | tech-startups run #2 | `company_category` (INSEE, group-level) — second subsidiary signal (caught traqfood → Mérieux) |
| 0.3.0 | — | enrich-buying-committee shipped (doctrine + verified waterfall) |
| 0.3.1 | relance-devis-habitat run (couvreurs) | `company_name` on contacts (readable table), kill-rule scope pattern (no invented statuses), postal-code API filter (resolved 4 trade-name artisans; the historic "Merci" ambiguity now high-confidence) |
| 0.4.0 | person-profile strategy review — live test proved FullEnrich *searches* are FREE and return full profiles (title, seniority, linkedin_url, dated job history); Proxycurl shut down July 4 (LinkedIn lawsuit), SERP demoted to fallback | enrich-person-profile shipped (FullEnrich-search-first waterfall) + NEW brick signal-person (job change free / LinkedIn posts / company news) + Bright Data pro mode (`&pro=1` → `web_data_linkedin_*` tools) |
| 0.4.1 | relance-devis-habitat person-profile run #1 — 7 free profiles via FullEnrich search; 6 SERP credits → 0 hits on domain-less artisans; "Gérant" labeled Manager by the provider; kill-flagged SOPREMA claimed-then-reverted; a contact row added mid-run | rung B opt-in on low-presence segments (no domain + tiny/artisan) · French legal titles → C-Level over provider labels · kill flags in memory/ exclude from scope pre-score · enrich bricks never create rows (receipt suggestions only) · one upfront paid-budget confirmation per run |
| 0.4.2 | signal-person fixture run (Julia Levy, tech-startups) — the move relay made person-profile write her Doctrine title onto her Predictice-anchored row; the planted signal (9 months old) was presented like fresh news; paid passes thin on a quiet profile | move ≠ promotion: a company change sets `left_company=1` (row frozen, excluded from person-profile AND write-sequence scopes), only promotions relay `profile_status` · `freshness` on every signal (≤60 days = fresh/icebreaker, older = context; write-sequence enforces it) · NEW hiring pass via `web_data_linkedin_job_listings` — often the strongest intent signal |

Full pipeline validated in the field at **0 credits** end to end:
sourcing (FullEnrich free preview) → firmographics (official API) →
one verified decision-maker per company (registry + free searches).

### To build — Robin (data in)

signal-person hiring pass v2 (France Travail API) · signal-sillage

> Considered & rejected: **enrich-company** — a standalone "enrich a company"
> brick would duplicate the generic `enrich` skill (any company column via
> FullEnrich / web content) plus `enrich-firmographics` (the structured
> subset). Rule 1 forbids the overlap. If international firmographics ever
> needs its own path, extend `enrich-firmographics`, don't fork a new brick.

### To build — Rémi (data out)

onboard · score-kill-gate + score-icp-fit · crm-import · crm-push ·
outreach-send (+ send-guard hook + workspace permission allowlist)

### Thomas (10%)

Docs site live + a generator compiling every `BRICK.md` into the docs
catalog (reference pages that can never drift) · GitHub issues board (one
issue per brick, assign = claim) · demo script.

---

## 4. Block contracts — IN → OUT + strategy

### Shipped blocks

**workspace** (Rémi ✅)
- IN: a name/goal from the user, or nothing (auto-resolution).
- OUT: `bricks/workspaces/<name>/` scaffolded (context/, bricks.db,
  staging/, memory/), current workspace set, banner displayed.
- Strategy: pure plumbing via `workspace.py` — deterministic script, no LLM
  judgment. The SessionStart hook re-displays the banner so the user always
  knows which world they are in.

**find** (Rémi ✅, patched)
- IN: target criteria (user + `context/icp.md`).
- OUT: `companies` (name, domain, source, status) / `contacts` rows,
  deduped on domain/email.
- Strategy: source priority — FullEnrich search when connected (free
  preview 10 + count, then money gate) for firmographic segments; Bright
  Data / directory scraping for niche local commerce; web search last, with
  domain verification. Receipt states which source was used and why.

**enrich** (Rémi ✅, patched)
- IN: rows with `X_status='pending'`, the column(s) to fill, the source
  kind.
- OUT: filled cells + statuses, columns created on the fly.
- Strategy: two source families — FullEnrich MCP for contact/firmographic
  data (hard gate: never fabricate, never scrape around it); Bright Data
  `scrape_as_markdown` for web-content columns (WebFetch fallback for
  simple pages, auto-retry blocked rows through Bright Data once).
  Batches of 5-8 rows, up to 10 subagents in parallel, each writing via
  db-writer as results arrive.

**transform** (Rémi ✅)
- IN: an existing table + an instruction (dedupe, filter, derive, score…).
- OUT: modified/derived rows or tables.
- Strategy: express the transform as db-writer operations; deterministic
  rules first (SQL-able), judgment only for ambiguous leftovers.

**scan-mentions** (Rémi ✅)
- IN: one question about one company's website.
- OUT: a short evidence-backed answer in the conversation (no table write).
- Strategy: Bright Data site scan (JS + anti-bot), quote the evidence,
  answer directly — the one brick whose output is conversational by design.

**interface** (Rémi ✅)
- IN: nothing.
- OUT: the local web UI on 127.0.0.1:4321, live view of every table.
- Strategy: `front/server.py` imports the same `db.py` module the skills
  use — UI and engine cannot disagree. Auto-refresh, row selection/delete.

**find-directory-scrape** (Robin ✅)
- IN: a directory/exhibitor-list/listicle URL (or a description resolved
  via search_engine + user confirmation).
- OUT: `companies` rows, `source='directory:<host>'`, deduped on domain;
  domain-less entries name-checked, never guessed.
- Strategy: Bright Data `scrape_as_markdown` (JS + anti-bot delegated,
  hosted endpoint — no local install). Scout page 1 → announce plan
  (pages × ~1 credit, caps 10 pages/200 entries) → subagents scrape page
  batches into staging JSONL → validate → db-writer commits. Optional
  second pass for detail pages (`scrape_batch`).

**find-lookalike** (Robin ✅)
- IN: seed customers = `companies WHERE segment='seed'` (from crm-import,
  CSV or dictated list; collected by the skill if absent) + their enriched
  columns.
- OUT: candidate `companies` rows, `source='lookalike:<seed-domain>'`;
  seeds never modified, seed domains never become prospects.
- Strategy: seeds live IN the companies table so every enrichment brick
  (present and future) sharpens the pattern for free. Read everything the
  seeds have, state the pattern + discriminating signal, get user
  confirmation BEFORE searching, then 3-5 similarity queries per seed
  (search_engine or web search), subagents → staging → validated commit.
  Full motion (enrich-first) belongs to playbook-lookalike.

**write-sequence** (Robin ✅)
- IN: `contacts` with `email_status='done'` and pending sequence; parent
  company pitch/language; `context/offer.md` (hard gate) + personas.
- OUT: 3 `messages` rows per contact (step 1/2/3, send_day 0/3/7,
  `status='draft'`, `msg_key` dedup) + `sequence_status='done'`.
- Strategy: the strategy is IN the context — the skill applies personas and
  proof points, never invents facts. Step 1 icebreaker anchored in enriched
  data, step 2 proof point new angle, step 3 short breakup. ≤120/120/60
  words, company's language, one example shown, drafts forever until a
  human approves.

**playbook-lookalike** (Robin ✅)
- IN: best customers from ANY source (CRM credential detected by shape,
  CSV, dictated).
- OUT: a filtered lookalike list matching the discriminating signal.
- Strategy: 5 phases through the bus — import seeds → enrich them with
  every installed enrichment brick (runtime discovery) → analyze + confirm
  the discriminating signal with the user → source candidates (lookalike /
  FullEnrich filters / directories) → re-enrich candidates on the
  discriminating column(s) only, cheapest first, and keep the matches.
  Two human checkpoints; resumable at every phase.

### Shipped since — Robin

**enrich-firmographics** ✅
- IN: `companies.name` (+ optional city/postal/domain hints),
  `firmo_status='pending'`.
- OUT: `employees`, `industry`, `naf`, `siren`, `city`, `executives`
  columns (+ `firmo_source='estimate'` for pass-3 grade data).
- Strategy: pass 1 — ONE batched call to `tools/firmo.py` hitting the
  official French government API (recherche-entreprises.api.gouv.fr):
  free, no key, self rate-limited, impossible to block — resolves most
  rows in seconds, executives included. Pass 2 — ambiguous names only:
  Bright Data reads the site's legal page (SIREN is legally published
  there) to pick the right record, ~1 credit/row. Pass 3 — non-French:
  site + public LinkedIn estimate, flagged. Cheap columns → run early,
  feeds the kill gate AND enrich-buying-committee.

**enrich-buying-committee** ✅ — full functioning

- IN: firmographics-enriched companies (`employees`, `executives`,
  `parent_company`, `company_category`, `committee_status='pending'`) +
  `context/offer.md` + `context/icp.md` (Buying roles) + `personas/`.
- OUT: ONE verified contact per company in `contacts` (`full_name`,
  `role` = actual title, `role_type` = `decision-maker` | `champion`,
  `linkedin_url`, `source` = which rung found it), `committee_status` →
  `done | not_found | failed`, `targeting_plan` persisted in
  `memory/state.json`.

*Phase 0 — the targeting doctrine (once per workspace, user-confirmed).*
Derived from offer + ICP + personas, presented in 5-6 lines, confirmed
by the user BEFORE any hunting, then persisted and reused silently on
re-runs (re-asked only if context/ changes):

| Company size | Target type | Why |
|---|---|---|
| ≲ 20 employees | decision-maker (founder/gérant/CEO) | no real champion exists in a 10-person shop — aim at the nerve |
| mid-size | decision-maker of the buying function | title patterns from the ICP (head of purchasing, head of sales…) |
| large + expensive/complex offer | CHAMPION first | the operational believer sells internally; personas say who |

One target type per company — never both. The plan also fixes the title
patterns per type (in the company's language) and the fallback rule:
`none` (strict, default) or `other_type` (take the other role, labeled).

*Phase 1 — the waterfall (per company, cheapest first, stop at first
VERIFIED hit).*

| Rung | Source | Cost | Skipped when |
|---|---|---|---|
| A | registry relay — the human in `executives` | free, instant | target ≠ decision-maker, company not small, or officer is a company (`parent_company` set → group noted) |
| B | FullEnrich people search (title patterns + domain) | free — searches cost no credits | FullEnrich not connected |
| C | LinkedIn via Bright Data SERP — `site:linkedin.com/in "<title>" "<company>"`, indexed snippets only, never logged in | ~1 credit, max 2 queries | Bright Data not connected |
| D | team/about page scrape | ~1 credit | — |

Verification rule at every rung: name + role + company must cohere IN
THE SOURCE ITSELF; ambiguity → next rung; nothing after D → fallback
rule, else `not_found`. Never an invented or unverified person. Writes
happen immediately per company via db-writer; dedup on
(company_id + full_name). Volume mode (>10 companies): subagents run
rungs B-D in parallel batches → staging JSONL → main thread verifies →
db-writer commits; SERP credits announced first (§8).

*Test protocol (validated fields on the tech-startups workspace):*
0. `relance enrich-firmographics` first if the table predates the
   contract columns.
1. "trouve les bons contacts pour mes entreprises" → the PLAN must be
   presented and await confirmation (hunting before OK = fail).
2. Rung A: ~6 small companies → instant free contacts from the registry
   (`source=registry`, `role_type=decision-maker`).
3. The hard case (Predictice): president is a holding (FORSETI) →
   registry skipped WITH the group noted → human CEO found via B/C with
   `linkedin_url` and announced credit.
4. Champion path: add a 100+ employee company (e.g. doctrine.fr) → plan
   routes to `role_type=champion` with an operational title.
5. Negative: a fictitious company → cascade exhausted →
   `not_found`, zero invention (the refusal IS the success).
6. Idempotence: re-run → done rows untouched, plan reused without
   re-asking.
Success checklist: one contact per company · role_type matches the plan
· every contact traced to its rung · credits announced before spending ·
receipts only in the conversation.

**enrich-person-profile** ✅ (0.4.0 — strategy revised after live tests)
- IN: `contacts` with `full_name` + a resolvable company (name/domain
  hints; an existing `linkedin_url` upgrades the lookup),
  `profile_status='pending'`.
- OUT: `role`, `seniority`, `linkedin_url`, `profile_source`;
  `profile_status` → `done | not_found | failed`.
- Strategy: verified waterfall, cheap first. Rung A — FullEnrich people
  search: FREE (0 credits, live-verified) and returns title, seniority,
  linkedin_url and dated job history — the "FullEnrich = only
  email/phone" belief was wrong: that is the paid *enrich* side, not
  *search*. Rung B — LinkedIn SERP via Bright Data, indexed snippets
  only (~1 credit; profile pages sit behind the login wall — confirmed,
  never scraped). Rung C — team/press pages. Optional structured rung:
  `web_data_linkedin_person_profile` (pro mode) when the URL is known
  but the title still missing. Name + role + company must cohere in the
  source; `not_found` over guessing. Completes imported/CRM contacts
  that enrich-buying-committee never touched. 0.4.1 field patches:
  rung B opt-in on low-presence segments (no domain + tiny/artisan),
  French legal titles → C-Level over provider labels, kill flags in
  memory/ excluded from scope, receipt suggestions instead of row
  creation, one upfront paid-budget confirmation per run. 0.4.2:
  `left_company=1` rows out of scope; the verification rule has
  primacy over any relay — a title observed at another company than
  the row's is never written.

**signal-person** ✅ (0.4.0 — new brick, person-level twin of signal-sillage)
- IN: contacts with `linkedin_url` (+ a resolvable company for
  hiring/news); scope = tier A/B once score exists, else
  user-confirmed; re-scan window: `signal_status='pending'` or
  `signal_checked_at` > 7 days.
- OUT: `signals` rows (`kind` = `job_change | new_post | hiring |
  company_news`, summary + `evidence_url` + date + `freshness` =
  `fresh` ≤60d | `context`, append-only, dedup on `sig_key`) +
  `contacts.last_signal` / `signal_status` / `signal_checked_at`. A
  PROMOTION resets the contact's `profile_status='pending'` (bus relay
  to enrich-person-profile); a company CHANGE sets `left_company=1`
  instead — row frozen, excluded from person-profile and
  write-sequence scopes, following the person is the user's call
  (0.4.2, field-tested on the Julia Levy fixture).
- Strategy: four announced passes, cheap first — job changes via FREE
  FullEnrich re-search (returned current employment vs stored columns;
  promotions count); recent posts via `web_data_linkedin_posts`
  (per-record, cap 25/run, money gate §8); hiring via
  `web_data_linkedin_job_listings` (per-record, cap 25 companies —
  often the strongest intent signal of the four); company news via
  SERP (last month, one query per company). A signal without a source
  URL/record does not exist; only FRESH (≤60 days) signals are
  icebreaker material. On-demand today; scheduled `claude -p` cadence
  next; real-time = cockpit V2. Prospect *comments* stay out of reach
  without a logged-in account — deliberately renounced (doctrine:
  never log in).

### To build — Robin (data in)

**signal-person — hiring pass v2 (rework)**
- Trigger (0.4.2 field test): detecting hiring through Google SERP is
  the wrong altitude — date-filtered queries came back 9/9 empty,
  undated ones are noise; and LinkedIn Jobs misses artisans entirely
  (they post on France Travail / Indeed / HelloWork).
- Strategy: official API first — the same doctrine that made
  enrich-firmographics unblockable. France Travail "Offres d'emploi"
  API (francetravail.io, free key): pull a company's live openings —
  by SIRET if the endpoint allows it (we already store `siren` via
  enrich-firmographics, column relay), else name+commune (exact param
  to validate at build time). Rung 2: `web_data_linkedin_job_listings`
  for bigger/tech companies only. SERP dropped from the pass. To
  evaluate on the same platform: La Bonne Boîte API
  (hiring-probability per establishment — a signal even when no offer
  is posted).
- One-time setup: a free France Travail API key, stored like the
  Bright Data token.

**find-company-people** (user-requested as `find-people-company`)
- IN: `companies` rows already in the DB (`domain` ideally),
  `people_status='pending'`, `status != 'disqualified'` + a role/title
  pattern (from the user or `context/icp.md` Buying roles / `personas/`).
- OUT: MULTIPLE `contacts` rows per company — `company_id`, `full_name`,
  `role`, `linkedin_url`, `email` (optional), `source` — deduped on
  (company_id + full_name/email); `companies.people_status` →
  `done | not_found | failed`. Optional per-company cap on N.
- Strategy: the "expand one company into its roster" brick — deliberately
  the OPPOSITE end from enrich-buying-committee. Where buying-committee
  returns ONE opinionated target per the plan, find-company-people returns
  the full matching SET when the user wants breadth (multi-threading,
  several stakeholders). Cost-ordered like the committee waterfall but
  without the "stop at first hit": FullEnrich people search (free) for the
  title pattern + domain → LinkedIn SERP via Bright Data
  (`site:linkedin.com/in "<title>" "<company>"`, indexed snippets only,
  never logged in, ~1 credit/query, capped) → team/about page scrape.
  Announce the volume (N companies × cap) under the money gate §8 before
  spending. Verify name + role + company cohere in the source; unverifiable
  → skip, never invent. Feeds enrich-person-profile (roster → per-person
  enrichment) and write-sequence. Boundary is explicit so Claude never
  confuses the two: committee = pick THE contact; find-company-people =
  list ALL matching contacts.

**signal-sillage**
- IN: qualified accounts (tier A/B once scoring exists).
- OUT: signal rows + companies flagged "wake up" for re-score/sequence.
- Strategy: step zero is the access spike (account, API key, docs). Then
  `sync` pushes the account list; `ingest` polls on demand or via a cron
  `claude -p` run (real-time webhook = cockpit, V2). Demo plan B: simulated
  signals in fixtures, clearly labeled. Person-level LinkedIn signals
  are already covered by signal-person (0.4.0) — this brick stays
  account-level.

### To build — Rémi (data out)

**onboard**
- IN: a conversation with the user (+ won customers when crm-import
  exists).
- OUT: filled `context/offer.md`, `icp.md`, `personas/*.md` and
  `scoring.yaml` (weights + kill rules).
- Strategy: interview, then propose — the agent drafts, the user validates.
  When seed customers exist, derive the ICP from facts (what the winners
  share) rather than declarations. Writes files, not database rows: this is
  the one brick whose OUT is the context itself.

**score-kill-gate + score-icp-fit**
- IN: cheap enriched columns + `context/scoring.yaml`.
- OUT: kill gate → `status='disqualified'` (early-stop: no brick ever
  spends on these again); icp-fit → `score` 0-100, `tier` A/B/C, `reasons`.
- Strategy: the agent writes the rules once (onboard), a deterministic
  pass applies them — same input, same score, explainable to a jury.
  Kill gate runs as early as columns allow (money gate's best friend);
  scoring re-runs free after every enrichment wave.

**crm-import**
- IN: a CRM credential/URL/export (HubSpot `pat-…`, Notion `ntn_…`,
  Salesforce org, Pipedrive, or CSV).
- OUT: won customers as `companies` rows with `segment='seed'`,
  `source=<crm>`.
- Strategy: detect the system from the credential shape; one thin connector
  per CRM (HubSpot and Notion have official MCPs — start there), all
  writing the same seed rows. CSV works today as the universal fallback.
  This brick is what makes find-lookalike CRM-agnostic.

**crm-push**
- IN: qualified rows (scored, or replied once outreach exists).
- OUT: account + contact (+ deal) created in the user's CRM, `crm_id`
  written back.
- Strategy: same connector layer as crm-import, reversed. Dedup against
  the CRM before creating (domain normalization), never create twice —
  `crm_id` present = skip.

**outreach-send** (+ send-guard hook + permission allowlist)
- IN: `messages` with `status='approved'` ONLY + mailbox credentials +
  quotas.
- OUT: `status='sent'`, send timestamps; bounces flagged.
- Strategy: sending is code, not judgment — a throttled deterministic
  sender (quotas per mailbox, spacing, send windows). A PreToolUse hook
  BLOCKS any send of a non-approved message mechanically — the guarantee
  is enforced, not promised. Ship the workspace permission allowlist in
  workspace.py scaffolding at the same time (no more permission popups on
  fresh workspaces).

---

## 5. Milestones

1. ~~Retest pass~~ — DONE: two field campaigns validated end to end
   (tech-startups, relance-devis-habitat), five product versions shipped
   from their findings.
2. **Score (kill gate + icp-fit) — THE next brick.** Kill rules are
   currently flagged everywhere but enforced nowhere; this brick turns
   them into the early-stop demo moment ("it stops spending on its
   own") and produces the tiers that prioritize emails, sequences and
   signal-person's paid passes.
   Rémi's per the split — Robin takes it if Rémi is still under water.
   **Onboard** (Rémi) upgrades the context-in-a-prompt into the guided
   interview.
3. **Full pipeline demo** on a real ICP: find → enrich → kill/score →
   contacts → emails → sequences, the table telling the story live.
4. **crm-import + playbook-lookalike** end-to-end (the differentiator vs
   Clay).
5. V2: cockpit (tabs UI), outreach-send with approval queue, Sillage
   real-time.
