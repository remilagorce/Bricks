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
│  db.py (dynamic Clay-style tables · single door, called direct) │
│  THE ENGINE: runner.py (loop) · researcher.py (1 agent/row)     │
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
- All database access goes directly through `db.py` (Rule 2 in
  CLAUDE.md), always with the absolute `bricks.db` path (`--db`).
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
| Plumbing: workspace.py, db.py (dynamic, called direct), session hook, front | Rémi | ✅ shipped, smoke-tested |
| CONVENTIONS §1-7 (workspace, drift, gates, statuses, staging, memory) | Rémi | ✅ shipped |
| CONVENTIONS §8 money gate + BRICK contracts | Robin | ✅ shipped (§8 v3 big-spend gate in 0.10.1 — Rémi ack pending) |
| Perf overhaul: db.py called direct (agent layer removed) + `claim` atomic + CONVENTIONS §9 waves-not-rows + parallel engines | Robin | ✅ shipped 0.11.0→0.14.0 (engine outputs proven identical; claim concurrency-tested; field run pending) |
| THE ENGINE: runner.py + researcher.py + web-researcher skill + CONVENTIONS §10-§11 (data plane, pilot wave) | Robin | ✅ shipped 0.15.0 (12-scenario mock bench green; real `claude -p` + Bright Data web lane: field run pending) |
| Engine `--action fetch` + fullenrich_people adapter (HTTP API, title-wave cascade) + find-company-people engine lane | Robin | ✅ shipped 0.16.0 (stub-API bench green: cascade, masked filter, dedup, child rollback; real API + key: field run pending) |
| workspace / interface / find / enrich / transform / scan-mentions | Rémi | ✅ shipped (find + enrich patched after test #1) |
| find-directory-scrape / find-lookalike / write-outreach / playbook-lookalike | Robin | ✅ shipped |
| enrich-firmographics (+ tools/firmo.py, official gov API) | Robin | ✅ shipped, field-tested ×2 |
| enrich-buying-committee (targeting plan + waterfall) | Robin | ✅ shipped, field-tested |
| enrich-person-profile (identity waterfall, FullEnrich-search first) | Robin | ✅ shipped, field-tested ×1 (0.4.1 patches) |
| signal-person (job change / hiring / posts / news scan) | Robin | ✅ shipped, field-tested ×2 (0.4.2 + 0.5.1 patches) |
| find-hiring-signal (pain-matrix job-post sourcing) | Robin | ✅ shipped, field-tested ×1 (0.5.1 patches; survived a full Bright Data outage at 0 credits) |
| tools/jobs.py (deterministic hunt engine: France Travail + HelloWork + career pages) | Robin | ✅ shipped, live-validated (reproduced both Gironde field runs, 0 credits, seconds) |
| tools/news.py (company-news engine: Google News RSS + warning flag) | Robin | ✅ shipped, live-validated (SOPREMA/Predictice/MORICEAU spread) |
| find-company-people (roster expansion, multi-threading) | Robin (spec Rémi) | ✅ shipped, field-tested ×1 (0.8.1 patches; 19 contacts / 0 credits) |
| plan-outreach (evidence-based strategy: motion / channels / cadence / tiers) | Robin | ✅ shipped, field-tested ×1 (0.9.1 patches; picked email-first on evidence) |
| playbook-outbound (deterministic full-motion dispatch, one chain GO) | Robin | ✅ shipped, field-tested ×1 (ran the milestone-3 pipeline end to end) |
| Bright Data + FullEnrich MCP wiring | Robin | ✅ shipped, both Connected |

### Field-test log — the loop that improves the product

Every fix below came from a real desktop test session. Plugin version at
head: **0.17.2**.

| Version | Trigger | What changed |
|---|---|---|
| 0.2.0 | stale-cache discovery (two sessions ran the pre-merge plugin) | CLAUDE.md Rule 3: version bump on every plugin change; merged plugin actually live |
| 0.2.1 | tech-startups run #1 | `parent_company` (holding detection, e.g. Predictice → FORSETI/Doctrine), siren-direct lookup, trade-name retry |
| 0.2.2 | tech-startups run #2 | `company_category` (INSEE, group-level) — second subsidiary signal (caught traqfood → Mérieux) |
| 0.3.0 | — | enrich-buying-committee shipped (doctrine + verified waterfall) |
| 0.3.1 | relance-devis-habitat run (couvreurs) | `company_name` on contacts (readable table), kill-rule scope pattern (no invented statuses), postal-code API filter (resolved 4 trade-name artisans; the historic "Merci" ambiguity now high-confidence) |
| 0.4.0 | person-profile strategy review — live test proved FullEnrich *searches* are FREE and return full profiles (title, seniority, linkedin_url, dated job history); Proxycurl shut down July 4 (LinkedIn lawsuit), SERP demoted to fallback | enrich-person-profile shipped (FullEnrich-search-first waterfall) + NEW brick signal-person (job change free / LinkedIn posts / company news) + Bright Data pro mode (`&pro=1` → `web_data_linkedin_*` tools) |
| 0.4.1 | relance-devis-habitat person-profile run #1 — 7 free profiles via FullEnrich search; 6 SERP credits → 0 hits on domain-less artisans; "Gérant" labeled Manager by the provider; kill-flagged SOPREMA claimed-then-reverted; a contact row added mid-run | rung B opt-in on low-presence segments (no domain + tiny/artisan) · French legal titles → C-Level over provider labels · kill flags in memory/ exclude from scope pre-score · enrich bricks never create rows (receipt suggestions only) · one upfront paid-budget confirmation per run |
| 0.4.2 | signal-person fixture run (Julia Levy, tech-startups) — the move relay made person-profile write her Doctrine title onto her Predictice-anchored row; the planted signal (9 months old) was presented like fresh news; paid passes thin on a quiet profile | move ≠ promotion: a company change sets `left_company=1` (row frozen, excluded from person-profile AND write-outreach scopes), only promotions relay `profile_status` · `freshness` on every signal (≤60 days = fresh/icebreaker, older = context; write-outreach enforces it) · NEW hiring pass via `web_data_linkedin_job_listings` — often the strongest intent signal |
| 0.5.0 | hiring rework (GTM playbook review) — SERP-guessing "does X hire?" was the wrong altitude, and hiring is TWO motions, not one: checking tracked companies vs sourcing new ones | signal-person pass 3 v2: segment-aware multi-source sweep (France Travail/Indeed/HelloWork SERP for artisans-SMB, ATS-direct + LinkedIn Jobs for tech; no date operators; agencies/stage excluded; CNIL company-level rule) + NEW brick find-hiring-signal (pain-matrix sourcing: one GTM hypothesis per query, offer extraction to staging, /100 signal score, commit ≥70 with a ready outreach angle) |
| 0.5.1 | first hiring field runs (Gironde) — Bright Data FULL outage (29/29 empty) absorbed by an improvised free-channel fallback at equal quality; 5-6 serial human gates per run made it painfully slow; ~135 interim offers filtered post-hoc; the morning's 8 signals rows missed `sig_key` | free-channel fallback + 1-credit health control promoted to doctrine (the doctrine is the engine, not the vendor) · ONE GO per run (matrix+budget+cut in a single confirmation; free passes never re-ask) · negative keywords in queries (interim brands) · `sig_key` added to find-hiring-signal's commit list (bug) + backfill · per-pass freshness (one pass's stamp never blocks another) · batched db-writer dispatches (per phase/batch, never per row) · source notes (France Travail keyword pages, LinkedIn post-ID dates) |
| 0.5.2 | backfill receipt — the two hiring writers keyed `sig_key` with different URL conventions (normalized vs raw), a silent future-duplicate trap | canonical `sig_key` normalization written into BOTH skills (scheme/`www.` stripped, no trailing slash); the 8 backfilled keys re-normalized in base |
| 0.6.0 | speed review — wall-clock went to LLM mechanical work (query generation, page fetching, card parsing) and serial human gates | `tools/jobs.py` shipped (hunt + check modes, stdlib-only: France Travail cards + detail microdata, HelloWork aria-labels, career-page probe, word-boundary agency filter ~40 brands + "recrute pour", prescore 65/100 with volume bonus); find-hiring-signal phase 1 and signal-person pass 3 now run the script FIRST, SERP/Bright Data demoted to escalation for ATS/LinkedIn lanes — hiring hunts cost ~0 credits and seconds on SMB/artisan ICPs (live-validated: both Gironde field runs reproduced) |
| 0.7.0 | script-the-plumbing continues | `tools/news.py` shipped (Google News RSS: free, no key, dated+sourced items, offer-term hits, distress `warning` flag for the kill gate; live-validated — SOPREMA 5 articles/45 j dont "CA record", 123 vieux articles filtrés, artisans QUIET honnêtes); signal-person pass 4 now script-first, SERP demoted to tier-A escalation; implementation note added to the score block: ship it as `tools/score.py` (the pattern is proven ×3) |
| 0.7.1 | free re-scan run #2 — the session still ran 0.6.0 (Rule 3 trap: opened pre-update; news.py untested); the re-scan downgraded 3 contacts carrying valid context signals; the AMB career-page signal duplicated (homepage vs deep page → two sig_keys) — both self-caught and hand-fixed by the run | career-page hiring signals key on the DOMAIN (one per company; board offers keep full URLs) · jobs.py career probe now prefers the deep page over the homepage · downgrade rule: `not_found` only when no valid signal rows exist, else re-scans close `done` |
| 0.7.2 | merge with Rémi's main — both sides had shipped a different "0.6.0" (version collision on rebase) | post-merge bump to a version neither cache has ever seen (Rule 3: a stale "already at latest" would silently hide the merged half); Robin's 0.5.0→0.7.1 line and Rémi's work now live in the same tree |
| 0.8.0 | find-company-people questioned, then green-lit — the value case is the single point of failure: dead threads (SERBER's Thouvenin, spotted by committee but contractually left at the receipt), `left_company` refills (Julia Levy), collective deals on mid-size | find-company-people shipped on Rémi's spec (roster waterfall WITHOUT stop-at-first-hit, cap 4/company, single GO) + masked-name rule (provider-masked last names never inserted) + thin-row relay to person-profile |
| 0.8.1 | roster field run #1 — the brick worked (19 contacts / 17 companies / 0 credits, Thouvenin in, masked names resolved via registry on the re-run, kill gate live: 4 disqualified auto-excluded) BUT the session peppered the user with trailing "veux-tu enchaîner ?" questions, paused on a user-named absent company, and burned 19 calls into a documented-dead Bright Data channel | receipts end with STATEMENTS, never questions (all Robin's bricks) · chain GO: follow-on bricks named in the request are budgeted in the single plan, zero mid-chain confirmations · user-named absent company auto-added (`source='user'`, flagged) · NEW rung A-bis: registry executives via `tools/firmo.py` (full first names — resolves initial-only site mentions) · workspace outage notes gate paid rungs to the free channel |
| 0.8.2 | chain-GO field run #1 — the design WORKED (1 plan / 4 budget lines / 1 GO / 0 questions / budgets reconciled honestly / receipt in statements) but the "GO sec" made write-outreach violate its own hard gate: 21 drafts with placeholders its contract forbids | precedence rule: a chain GO never overrides a downstream brick's HARD gate — satisfy it at plan time (fold the missing input into the single GO) or end the chain before that brick, stating what is missing. Candidate for CONVENTIONS with the whole anti-friction set (receipts-no-questions, chain GO) — shared surface, needs both approvals |
| 0.9.0 | strategy-layer design (2026 GTM corpus review with Robin) — write-sequence only wrote 3 emails and NOBODY decided the channel; "who is the orchestrator?" answered: the session (auto-delegation) or a playbook (explicit dispatch), never a brick, and bricks never talk to each other — artifacts on the bus | NEW plan-outreach (evidence-based strategy → `context/strategy.md` + `contacts.channel_plan`) · write-sequence RENAMED **write-outreach** and extended multi-channel (email + linkedin-invite/dm, CPPC doctrine, `voice.md` sender voice, strategy.md hard gate) · NEW playbook-outbound (deterministic full-motion dispatch, one chain GO, resumable) · all cross-references renamed |
| 0.9.1 | strategy-layer field run #1 = the milestone-3 pipeline ran end to end on relance-devis-habitat (21 companies → firmo → strategy on evidence [email-first for artisans, decided on 66,7 % LinkedIn / 0 % email coverage] → 104 drafts → 16 send-ready, ≈16 credits, budgets held) — three slips: a disqualified company's contact got a channel_plan (caught downstream), email drafts written before addresses existed (user-consented but contract said otherwise), the signature was INFERRED from the machine username | channel_plan exclusion moved to assignment time · email-drafts-before-address = explicit GO opt-in (default: wait) · signatures are never inferred — re-ask the single missing field |
| 0.9.2 | Robin's doctrine call on the drafts | LinkedIn invitations carry NO note, ever (corpus rule: add without a message, the profile does the credibility work) — the `linkedin-invite` row becomes an action item, not copy; the 19 written invite notes cleaned in base |
| 0.10.0 | validation-fatigue review (Robin): §8's "explicit confirmation, silence is not consent" made every small spend a question; safety requirement = autonomous spend must stay SMALL, never "des 100 et des 1000" | CONVENTIONS §8 v2 — the autonomy envelope: free/small runs (≤ `context/budget.md` per_run, default 15 credits) run announced-but-UNASKED; beyond → ONE grouped GO with fallbacks; HARD ceiling 50/run + 200/week that only a human hand-edit of budget.md can raise; business inputs asked once per workspace, persisted. All 7 Robin bricks re-pointed to §8 v2. **Rémi ack pending on the CONVENTIONS diff** (shared surface) |
| 0.10.1 | Robin's correction on 0.10.0 — no per-run/per-week envelopes, no bookkeeping: full autonomy ALWAYS, one question ONLY when a lot of credits go out at once | §8 v3 "big-spend gate": single threshold (default 50 credits per batch/action, user-adjustable by saying it — `spend_threshold` in state.json), silent below with spend + session cumulative in receipts, ONE grouped batch GO above ("les ~100 prochains ≈ 100 crédits — GO ?"); budget.md, weekly ceilings and run-cap list removed; bricks re-pointed |
| 0.11.0 | perf audit #1 (Robin: runs felt "ligne après ligne") — the biggest hidden cost was the db-writer SUBAGENT: a full cold model round-trip (~15-25 s) to run a <100 ms deterministic command, ×12-20 dispatches per enrichment run = minutes of pure JSON-shuttling; the anti-drift rationale (one file knows db.py's CLI) never required an agent, only a single reference | db-writer agent REMOVED — skills call `db.py` directly (Bash, same as workspace.py/firmo.py); CONVENTIONS §5 becomes THE single CLI contract (count/schema/drop-* folded in; `--db <absolute path>` mandatory); CLAUDE.md Rule 2 rewritten; subagents write staging only, the main thread commits |
| 0.12.0 | perf audit #2 — per-row waterfalls serialized N × network latency (row 1 rungs A→B→C, then row 2…), and volume mode spawned cold-start subagents from 10 rows | CONVENTIONS §9 "waves, not rows": one rung × whole batch fired IN PARALLEL in one message; batch tool variants preferred (`enrich_bulk`, `search_engine_batch`, `scrape_batch`); cost order preserved BETWEEN waves (§8 untouched); ONE db.py write per wave (iron rule 1 amended); subagent threshold ~10→~40; progress lives in statuses, the front reads live — 8 bricks re-pointed |
| 0.13.0 | perf audit #3 — the deterministic engines were batch but fetched SERIALLY (0.16-0.8 s sleep between requests: pure I/O wait, CPU asleep) | firmo/jobs/news parallelized: ThreadPoolExecutor behind shared rate limiters (global for the gouv API — it counts req/s, not concurrency; PER-HOST for jobs politeness), all pacing centralized in fetch(), `--workers` flags (6/6/4), results assembled in input order — outputs proven byte-identical serial vs parallel on live runs (firmo 6 cos, news 4 cos, jobs 100 raw offers) |
| 0.14.0 | the select-then-mark claim pattern was 2 round-trips AND a race window: two parallel runs could claim the same pending rows between the select and the mark | `db.py claim <table> <status_col>`: atomic select + mark-running in one BEGIN IMMEDIATE transaction (concurrency-tested — 4 parallel claimers, 20 rows, zero overlap); disqualified rows never claimed, `--retry-failed` for explicit retries; §5 iron rules 1-2 re-anchored on claim |
| 0.15.0 | architecture review with Robin (Claygent model) — three fears named: 5 000 wrong rows discovered too late, MCP bulk data rotting the session context, per-skill iterators multiplying; plus the field truth that any per-row question should be enrichable without a specialized brick | THE ENGINE shipped: `tools/runner.py` (the only loop — claim by tranches with a per-run re-claim guard, `{{column}}` merge validated BEFORE spend, actions `agent`/`set`, wave writes, reconciled receipts, `--preview 10` in-base + rollback by run manifest + `release` for crashed rows, workers hard-capped ~10) + `tools/researcher.py` (ONE disposable agent per row, `claude -p` default / `BRICKS_WORKER_CMD` override, Bright Data MCP optional `--tools web` capped by `--max-pages`, structured multi-field answers validated, never invents) + NEW skill web-researcher (any question → columns; ≲5 rows stay in-session) + CONVENTIONS §10 control/data plane (the "does the model need to READ it?" test, FullEnrich CSV exports mandatory >~20 rows, sponge subagents, pilot wave) + §11 engine contract + CLAUDE.md Rule 4. 12-scenario mock bench green (template refusal pre-spend, preview/commit/idempotence, retry no-loop, rollback, release, set, error columns); real `claude -p` auth unavailable in the build sandbox — field run pending |
| 0.16.0 | find-company-people questioned again: the MCP search is a 10-result preview capped per call and everything ran in session; Robin's requirements — FullEnrich's HTTP API in the usual Python loop, intelligence in the QUERY (title synonyms of the same activity, cascade "not found with kw1 → retry kw2", never semantic drift: GTM engineer ≠ SDR), reuse the SAME runner (arguments differ, scripts don't) | engine `--action fetch` shipped: `tools/fetchers/` adapter contract (`fetch(row, params) → {status, rows, evidence, credits}`) + `fullenrich_people.py` (POST /api/v2/people/search verified in their docs — Bearer `FULLENRICH_API_KEY`, `current_company_domains`/`current_position_titles`/`current_position_seniority_level`, shared rate limiter; title-WAVE cascade per group, stop at first verified wave; accept rules: current-employment domain match, masked names never inserted; per-call `metadata.credits` summed into the receipt) + runner `--out-table` child-row inserts (dedup `person_key`, `source_run` tag, thin-row relay `profile_status='pending'`, rollback now removes child rows) + find-company-people engine lane (params compiled ONCE — strict-synonym doctrine, groups per explicit role; session sweep kept as no-key fallback). Stub-API bench green: cascade vague1→vague2, masked filter, wrong-domain filter, dedup across runs, child rollback, idempotence, agent/set regression |
| 0.16.1 | first desktop field run of the engine (gtmia-agent workspace) — the WHOLE 0.15/0.16 flow held (drift guardrail → onboarding → find with CSV-export lane → import → interface → prompt compile → preview) EXCEPT the workers: desktop's sandboxed Bash cannot read the macOS Keychain, so nested `claude -p` answered "Not logged in" (the preview failed clean: rows reset, zero spend — the failure path worked as designed); Robin is desktop-only, keys must live in files, not per-session exports | `tools/envfile.py` shipped: the engine self-loads `~/.bricks/env` (KEY=value, chmod 600, outside every repo) at import — worker auth via `CLAUDE_CODE_OAUTH_TOKEN` (one-time `claude setup-token`) OR `ANTHROPIC_API_KEY` (browser-created, API billing — the zero-terminal path), plus `FULLENRICH_API_KEY`, `BRIGHTDATA_API_TOKEN`; shell exports keep precedence; researcher + fetchers wired, template file scaffolded on the user's machine; bench: fetcher key from file only ✅, worker inherits token from file ✅, shell precedence ✅ |
| 0.17.1-0.17.2 | authors credit (Robin added) + Robin: each key in the panel must say EXACTLY where to obtain it | manifests author « Rémi Lagorce & Robin Jehanno » · KNOWN_KEYS carry `how`/`url`/`command` (clickable console.anthropic.com → API Keys, app.fullenrich.com, brightdata.com/cp; `claude setup-token` shown as a copyable chip) rendered under each key in the ⚙ modal — live-preview verified |
| 0.17.0 | Robin: keys must be manageable WITHOUT files-and-terminal gymnastics — auto-recognized, asked for when missing, and visible/editable in the front behind a settings gear | `envfile.py` grew `status`/`set` (CLI + module — values ALWAYS masked to their last 4 chars, unknown keys rejected, commented placeholders replaced in place, chmod 600 kept) · front: ⚙ topbar button + settings modal (per-key status dot, label + where-to-get-it hint, paste-and-save input; POST `/api/settings` never echoes values) · server: GET/POST `/api/settings` reusing envfile as the single door · doctrine §11: missing key → ask in chat (provider keys only — the OAuth token NEVER transits the chat) → `envfile.py set` → re-run; interface skill mentions the gear. Bench: CLI roundtrip ✅, endpoints ✅ (bad key → 400, full value absent from every response), UI save flow verified in live preview ✅ |

Full pipeline validated in the field at **0 credits** end to end:
sourcing (FullEnrich free preview) → firmographics (official API) →
one verified decision-maker per company (registry + free searches).

### To build — Robin (data in)

signal-sillage

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
  Batches of 5-8 rows, up to 10 subagents in parallel, each appending
  findings to staging as results arrive; the main thread commits via db.py.

**transform** (Rémi ✅)
- IN: an existing table + an instruction (dedupe, filter, derive, score…).
- OUT: modified/derived rows or tables.
- Strategy: express the transform as db.py operations; deterministic
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
  batches into staging JSONL → validate → db.py commits. Optional
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

**write-outreach** (Robin ✅ — renamed + extended from write-sequence, 0.9.0)
- IN: `contacts` with `channel_plan` set (by plan-outreach) + pending
  sequence + the lane prerequisite (email lane: `email_status='done'`;
  linkedin lanes: `linkedin_url`); HARD gates `context/strategy.md` +
  `offer.md`; soft gate `voice.md` (the SENDER's voice — tu/vous, ton,
  interdits, signature; missing → defaults folded into the GO);
  personas (the RECIPIENT's angle) + fresh signals / `hiring_angle`.
- OUT: `messages` rows per step — `channel` = `email` |
  `linkedin-invite` | `linkedin-dm`, `send_day` from the strategy's
  template, `status='draft'` forever,
  `msg_key='<contact_id>-<channel>-<step>'` — +
  `sequence_status='done'`. Email drafts feed outreach-send later;
  LinkedIn drafts are copy-paste material (automated LinkedIn sending
  stays out by doctrine).
- Strategy: EXECUTES strategy.md, never invents positioning. CPPC
  (contexte → problème posé en sujet, jamais assené → UNE proposition
  → UNE question), email < 100 mots, LinkedIn = a chat (invite ≤ 300
  chars, DM 2-4 lines), plain subjects, personalization = one relevant
  signal connected to the problem (fresh signals + hiring_angle
  first), hot-manual tier = mini-audit opener, warm = feedback ask.
  Forbidden: talking about yourself, selling in the message,
  placeholders, invented facts.

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
happen immediately per company via db.py; dedup on
(company_id + full_name). Volume mode (>10 companies): subagents run
rungs B-D in parallel batches → staging JSONL → main thread verifies →
db.py commits; SERP credits announced first (§8).

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
  write-outreach scopes, following the person is the user's call
  (0.4.2, field-tested on the Julia Levy fixture).
- Strategy: four announced passes, cheap first — job changes via FREE
  FullEnrich re-search (returned current employment vs stored columns;
  promotions count); recent posts via `web_data_linkedin_posts`
  (per-record, cap 25/run, money gate §8); hiring via `tools/jobs.py
  check` (0.6.0 — free trade sweep + name check + career-page probe,
  agencies pre-flagged; Bright Data escalation for ATS/LinkedIn-only
  companies, cap 25 — often the strongest intent signal of the four);
  company news via `tools/news.py` (0.7.0 — Google News RSS, free,
  last-month window, distress `warning` flag; LLM judges homonyms;
  SERP escalation only for quiet tier-A accounts). A signal without a source
  URL/record does not exist; only FRESH (≤60 days) signals are
  icebreaker material. On-demand today; scheduled `claude -p` cadence
  next; real-time = cockpit V2. Prospect *comments* stay out of reach
  without a logged-in account — deliberately renounced (doctrine:
  never log in).

**find-hiring-signal** ✅ (0.5.0 — new brick: hiring as a sourcing engine)
- IN: `context/offer.md` + `icp.md` (HARD gate — the pain matrix
  derives from them) + Bright Data; confirmed `hiring_matrix`
  persisted in `memory/state.json`, reused silently.
- OUT: `companies` rows (`source='hiring-signal'`, verified domain,
  `hiring_score` 0-100, `hiring_angle` ready for write-outreach) + one
  `signals` row per company (`kind='hiring'`, freshness, evidence
  URL); raw offers + rejects in `staging/hiring-<date>/`.
- Strategy: you are not searching job ads — you are searching
  companies that just revealed a business priority in public.
  User-confirmed pain matrix (titles × tools × pains × geo; one GTM
  hypothesis per query, never "startup jobs France") → batched SERP
  over ATS-direct (greenhouse/lever/ashby/workable/teamtailor/WTTJ),
  LinkedIn Jobs, Indeed, France Travail + HelloWork for SMB ICPs →
  offers scraped and extracted to staging, filtered (≤60 days, real
  employer, no agencies/stage, CNIL company-level only) → grouped by
  company, signal score /100 (recency 20, category fit 25, tool 15,
  pain wording 15, volume 15, size 10) → user confirms the cut
  (default ≥70) → committed with the angle as contextual proof, never
  "j'ai vu que vous recrutez". Future upgrade to evaluate: France
  Travail official API + La Bonne Boîte (exhaustive per-SIRET
  coverage, free key). 0.5.1 field patches: single GO per run,
  1-credit health control + free-channel fallback, negative keywords,
  `sig_key` fix, batched commits.

**tools/jobs.py** ✅ (0.6.0 — the deterministic hunt engine)
- IN: hunt mode — the confirmed `hiring_matrix` JSON; check mode — a
  companies batch (`company_id`, name, domain, location) +
  `--keywords` trade terms swept ONCE for the whole batch (France
  Travail matches employer names poorly; the trade sweep is what
  finds them).
- OUT (staging only — never touches bricks.db): `offers.jsonl`
  (pre-extracted, prescore ≤ 65: recency/tools/pains/volume),
  `rejected.jsonl` (agencies, stage, expired, anonymous — with
  reasons, recoverable), `companies.jsonl` (grouped with volume
  bonus, or per-company `hiring`/`quiet` verdicts), `summary.json`
  (the receipt: counts, caps, errors, spend=0).
- Strategy: firmo.py doctrine — deterministic script, no LLM in the
  loop. Polite stdlib fetches (0.8 s rate, browser UA, one retry):
  France Travail search cards + detail microdata (datePosted,
  hiringOrganization, validThrough), HelloWork cards (aria-label
  carries title/city/company/contract), career-page probe on known
  domains (≤ 3 fetches); word-boundary agency filter (~40 interim
  brands + the "recrute pour" formula). Live-validated on day one:
  reproduced the manual Gironde hunt (104 raw → 34 kept, 24+ agencies
  flagged, MORICEAU's double offer caught by the volume bonus) and
  the afternoon hiring pass (AMB career page + MORICEAU via trade
  sweep) — seconds, 0 credits. The skills call it FIRST; SERP/Bright
  Data are the escalation for ATS/LinkedIn lanes.

**tools/news.py** ✅ (0.7.0 — the company-news engine)
- IN: a companies batch (`company_id`, name) + `--days` window +
  optional `--terms` (offer vocabulary).
- OUT (staging only): `news.jsonl` (dated items, outlet, URL,
  `term_hits`, `name_in_title`, `warning` on distress vocabulary —
  redressement/liquidation feed the kill gate, never an icebreaker),
  per-company `news`/`quiet` verdicts, `summary.json`.
- Strategy: Google News RSS (free, no key, FR edition), one fetch per
  company, legal-form suffixes stripped from the query phrase. The
  script filters by date and vocabulary mechanically; the LLM judges
  relevance (homonyms). Live-validated: SOPREMA → 5 dated articles in
  45 days ("CA record" caught by `croissance`), 123 older items
  dropped, no-press artisans honestly QUIET. signal-person pass 4
  calls it first; SERP only for quiet tier-A accounts.

**find-company-people** ✅ (0.8.0 — spec by Rémi, user-requested; built by Robin)
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
  enrichment) and write-outreach. Boundary is explicit so Claude never
  confuses the two: committee = pick THE contact; find-company-people =
  list ALL matching contacts. 0.8.0 implementation notes: ONE GO per
  run (pattern + cap [default 4] + scope + worst-case budget in a
  single confirmation); masked-name rule — FullEnrich-masked last
  names ("Hakim A.") are never inserted, resolved via rungs B/C or
  receipt-mentioned only; thin rows get `profile_status='pending'`
  (bus relay to enrich-person-profile); the committee's `role_type`
  is never touched; kill-flagged companies never claimed.

**plan-outreach** ✅ (0.9.0 — the strategy brick)
- IN: HARD gate `offer.md` + `icp.md` + `personas/`; EVIDENCE from the
  base (firmo columns, `tier` distribution — absent → uniform-degraded
  and stated, signal freshness, contact coverage: % linkedin_url,
  % verified emails, seniority mix) + 3 facts folded into the single
  GO (deal size, maturity pre-PMF/first-100/scaling, existing
  audience).
- OUT: `context/strategy.md` (motion, channel mix, cadence/volumes,
  per-tier treatment A hot-manual / B standard / C light, sequence
  templates per lane, the evidence behind each choice, date —
  user-confirmed once, persisted, re-proposed only on material
  change) + `contacts.channel_plan` = `email` | `linkedin` |
  `linkedin+email` | `hot-manual`, per row, evidence-based.
- Strategy: the team's 2026 GTM corpus distilled into a decision
  doctrine (pre-PMF → LinkedIn validation · first-100 → founder
  outbound, one channel deep · high-ticket → hot/ABM manual · high
  LinkedIn coverage → authority + invite→email · education market →
  content + warm email · existing audience → media system · PLG →
  bottom-up · physical → omnichannel). LinkedIn+email is the B2B
  default; email-only when the evidence says so (artisan ICPs). Runs
  AFTER enrichment/score — evidence, never vibes. Never writes a
  message: write-outreach executes, the orchestrator sequences.

**playbook-outbound** ✅ (0.9.0 — the deterministic orchestrator of the motion)
- IN: a workspace with context filled (TODO → dispatches gtm-onboard
  first) + ONE chain GO (per-phase counts, worst-case budgets, the 3
  strategy facts).
- OUT: the pipeline's artifacts, each written by its own brick;
  resumable phase log in `memory/state.json`.
- Strategy: explicit dispatch, fixed order — evidence (firmo →
  committee or roster → profiles) → score (kill gate + tiers;
  degrades gracefully if absent) → free signal passes → plan-outreach
  → write-outreach → human hand-over (approve email drafts,
  copy-paste LinkedIn ones). Runtime discovery of installed bricks;
  the only legitimate mid-chain stops are a strategy CONTRADICTION at
  the plan phase or an unplanned cost. This answers "who is the
  orchestrator?": the session auto-delegates for exploration; THIS
  playbook is the trusted, rerunnable version (CLAUDE.md dispatch
  doctrine).

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
  scoring re-runs free after every enrichment wave. Implementation
  note (0.7.0): ship the deterministic pass as `tools/score.py`
  reading `scoring.yaml` — the firmo/jobs/news pattern, proven ×3:
  script applies the rules, LLM only explains edge cases, db.py
  commits. The `signals` table (freshness, distress `warning`) is
  scoring input too.

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
   **First full run achieved 2026-07-06** (relance-devis-habitat:
   21 companies → firmo → 30 contacts → signals → evidence-based
   strategy → 104 drafts → 16 send-ready, ≈ 16 credits, one GO per
   brick). Remaining for the demo proper: the formal score brick in
   the loop + the live séance.
4. **crm-import + playbook-lookalike** end-to-end (the differentiator vs
   Clay).
5. V2: cockpit (tabs UI), outreach-send with approval queue, Sillage
   real-time.
