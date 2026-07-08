# Bricks — roadmap

The reference plan for the team. Architecture rules live in
`plugins/bricks/CONVENTIONS.md`; per-skill contracts in each skill's
`BRICK.md`. Read this file to know, in order: **where we are going**
(§1 target), **how we build** (§2 star), **where we are** (§3 status +
field-test log), **how the data actually flows — Python / session /
engine** (§4), **every brick IN → does → OUT** (§5 catalog), and **what's
next** (§6 milestones).

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
| Engine worker lanes: `worker_api.py` light worker + concurrency cap 10→50 + `haiku` default + calibrated-single-shot doctrine (escalation ladder tested & REJECTED) | Robin (engine = shared w/ Rémi) | ✅ shipped 0.18.0→0.20.1 (6 A/B runs on gtmia-agent; ladder lost on both workers; doctrine = single shot + `too_long`→`sonnet` recovery, worker = budget choice — Rémi review pending) |
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
head: **0.22.1**.

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
| 0.17.3 | gtmia-agent field run: the session's direct Bright Data calls returned empty for a whole run — diagnosed as TWO problems: (a) a dictated French sentence had been pasted into BRIGHTDATA_API_TOKEN via the ⚙ panel and silently accepted, (b) the desktop app (Finder-launched) never sees ~/.bricks/env so `.mcp.json`'s ${BRIGHTDATA_API_TOKEN} expanded empty for the SESSION connector (the engine lane was fine) | `envfile.set_key` now REJECTS whitespace / <8-char values (front + CLI, clear French error); bad value scrubbed; login LaunchAgent publishes the token to the GUI env via `launchctl setenv` (reads ~/.bricks/env, skips blank/whitespace/placeholder); real token re-pasted, validated live against the Bright Data MCP (`initialize` → HTTP 200, serverInfo brightdata-mcp); CONVENTIONS §11 documents the two-lane token model + the desktop fix |
| 0.17.1-0.17.2 | authors credit (Robin added) + Robin: each key in the panel must say EXACTLY where to obtain it | manifests author « Rémi Lagorce & Robin Jehanno » · KNOWN_KEYS carry `how`/`url`/`command` (clickable console.anthropic.com → API Keys, app.fullenrich.com, brightdata.com/cp; `claude setup-token` shown as a copyable chip) rendered under each key in the ⚙ modal — live-preview verified |
| 0.17.0 | Robin: keys must be manageable WITHOUT files-and-terminal gymnastics — auto-recognized, asked for when missing, and visible/editable in the front behind a settings gear | `envfile.py` grew `status`/`set` (CLI + module — values ALWAYS masked to their last 4 chars, unknown keys rejected, commented placeholders replaced in place, chmod 600 kept) · front: ⚙ topbar button + settings modal (per-key status dot, label + where-to-get-it hint, paste-and-save input; POST `/api/settings` never echoes values) · server: GET/POST `/api/settings` reusing envfile as the single door · doctrine §11: missing key → ask in chat (provider keys only — the OAuth token NEVER transits the chat) → `envfile.py set` → re-run; interface skill mentions the gear. Bench: CLI roundtrip ✅, endpoints ✅ (bad key → 400, full value absent from every response), UI save flow verified in live preview ✅ |
| 0.18.0 | perf study on gtmia-agent (Robin: web runs slow vs Clay) — A/B on engine concurrency (see the worker-lanes subsection below) | `--workers` cap 10→20 (default 12); agent rows default to `--model haiku` (was the CLI's heavy default) — the two cheapest speed/cost levers, matching Anthropic's effective-agents + multi-agent-research guidance |
| 0.19.0 | A/B RUN A vs B: 50 `claude -p` workers COLLAPSE (0 done — a heavy CLI per row oversubscribes the local Mac's CPU) while 12 hold (369s / 42-of-50 answered); per-row ≈88s so the cold-start is noise next to the web navigation | `--workers` cap → 50; NEW `tools/worker_api.py` — a lightweight Anthropic-API worker (no CLI cold-start, haiku, web via the API's server-side MCP connector, opt-in through `BRICKS_WORKER_CMD`); `researcher.py` exports the run context (model / tools / max-pages) to any override so a custom worker can drive the web lane too |
| 0.20.0 | A/B RUN C: `worker_api` HOLDS at 30 workers (133s, ~2.8× faster) where `claude -p` died at 50 — but it bills API credits and hit the account usage cap after 4 web runs; the escalation-ladder test LOST on `claude -p` (a low first timeout sits under the cold-start, and an internal double-retry doubles each timed-out row's cost) | `--no-retry-timeout` (fail a timed-out row on the first try so an escalation ladder pays 1× not 2×; default keeps the retry — backward-compatible, verified 2→1 attempts) + CONVENTIONS §11 worker-per-lane doctrine + the old wrong "workers are I/O-bound, ceiling = rate limit" line corrected (`claude -p` is local-CPU-bound) |
| 0.22.1 | A/B run-c (hiring-test-c, 0.22.0) — le crible figé a tenu sa promesse mécanique (étape 1 : 1558→573 s, curate 1,57 s sur 242 boîtes, cut relatif mesuré, 0 orphelin, override-par-exception exécuté comme écrit) MAIS le total est PIRE (2331 vs 2084 s) : 13/18 committed étaient des cabinets à noms modernes (Voluntae, Lynx RH, Sinclair Ressources, « super recruteur »…) → l'étape 2 a payé 11 vérifs web sérielles (1255 s). Le run-b avait APPRIS ces patterns dans son script jetable ; le gel du crible avait perdu ce savoir. Leçon : une liste de noms ne suffira jamais, quelle que soit l'industrie | Défense en profondeur, industry-proof : **(a)** `DESC_AGENCY_RE` dans curate — le langage recruteur dans le TEXTE de l'offre (« pour notre client », « nous recrutons pour », « cabinet d'expertise comptable ») attrape les marques opaques qu'aucun token de nom ne verra (Voluntae/Huca/Hermesiane testés) · **(b)** vague de vérification d'identité employeur AVANT commit (1 message parallèle §9, gratuit, cap 20 — borné en amont vs illimité en aval) · **(c)** tokens modernes dans NAME_AGENCY_TOKENS (talent·s, ressources, people, executive, rh, recrute, super recruteur… — 11/13 noms du run flagués, 0 faux positif sur les vraies PME dont Talentsoft) · **(d)** auto-apprentissage : les kill flags mémoire du workspace se replient dans `exclude_employers` à la compilation de la matrice — un cabinet démasqué ne repasse jamais · **(e)** rank volume même-kind : ≥2 signaux frais du même kind déclenchent le bonus (3 offres hiring ≠ rien ; testé 50 vs 40) |
| 0.22.0 | A/B scénario 2 (hiring-test-b, 0.21.3) — qualité ✅ partout (cut relatif annoncé puis re-calibré sur mesure, 0 signal orphelin, dédup idempotente, TYLS démasqué par le pass hiring, rank honnête « 0 now sans tier ») MAIS étape 1 = **1558 s vs 423 s** : le hunt n'a mis que 28 s — les ~25 min sont parties dans un script de curation `process.py` écrit À LA VOLÉE puis débuggé en live (regex sensibles à la casse → 105 vrais rôles finance rejetés à tort, 4 itérations), et ce script vit dans le staging du workspace → un workspace neuf le re-dérive de zéro, re-bugs compris. Le pattern exact rejeté pour rank-accounts | **La curation gelée dans le plugin** : NEW `skills/find-hiring-signal/scripts/curate.py` (Mode A — filtres nom staffing/cabinet + public/asso + méga-groupes + noms-artefacts, points de rôle finance 25 / terrain 15 casse/accents-insensibles via `norm()`, cut RELATIF **mesuré sur le batch** (reachable = 100 − critères improductibles, receipt montre reachable/cut/park + critères droppés), angle templétisé par groupe de rôle, payloads DB prêts ; `emit-signals` joint les `_id` et REFUSE d'écrire un signal sans `company_id`) + `jobs.py` NAME_AGENCY_TOKENS (cabinet attrapé par le NOM — « KEYSTONE RECRUTEMENT » a traversé DEUX runs — sans flaguer une PME qui recrute un chargé de recrutement) + SKILL Phases 2+3 réécrites : le jugement passe APRÈS le script, par exception, jamais en réécrivant le crible. Bench : fixture rejouant tous les pièges du run réel verte en 0,009 s (casse mixte matchée, KEYSTONE/mairie/Eiffage/artefact rejetés motivés, chaîne payload→db→ids→signals idempotente, garde anti-orphelin déclenche l'erreur). Attendu : étape 1 ≈ 26 min → ~2-3 min |
| 0.21.3 | re-run scénario 2 sur workspace neuf (hiring-test) — les fixes 0.21.1/0.21.2 ont tenu (signals nés avec company_id, dédup idempotente, statements, chrono relayé : hunt 31,5 s / check 110,8 s / étape 1 = 423 s dont ~390 s de curation en session) mais 5 findings : (1) le cut ≥70 absolu est inatteignable par construction sur un ICP PME (taille 10 pts invisible dans une annonce + bonus volume 15 pts réservé aux gros employeurs → plafond ~60 ; les DEUX runs ont improvisé ~45-50 — même dérogation à chaque run = règle fausse) ; (2) Michael Page/LHH/Comptalents/Cliff Partners ont traversé le filtre agences ; (3) les sweeps France Travail `<dept>D` → 301 → 410 (endpoint mort) ; (4) 92 % du wall-time de l'étape 1 = curation du bruit en session ; (5) l'agent a auto-rempli l'offre TODO depuis le goal (pragmatique mais non conforme au §3 écrit) | **#1** cut RELATIF : commit ≥ 65 % des points ATTEIGNABLES au sourcing (reachable = 100 − taille si invisible − bonus volume si ICP mono-offre ; ex. PME : 75 → commit ≥ 49), park 45-65 %, chiffres absolus annoncés au GO — la barre reste haute d'elle-même sur une chasse scaleup · **#2** 13 marques ajoutées au filtre word-boundary (michael page, pagegroup, lhh, comptalents, cliff partners, robert half, fed finance, robert walters…) — testé, zéro faux positif · **#3** `ft_location_code` émet le n° de département NU (vérifié live : `69D`→301→410, `69`→200 + 20 cartes ; les codes `D` fournis sont auto-strippés) · **#4** couvert par #2+#3 (moins de bruit → moins à juger) ; préfiltre grands groupes en réserve si insuffisant · **#5** doctrine §3 tranchée côté auto-fill : substance suffisante → v1 déduite ANNONCÉE et on avance (l'interview ne bloque plus un sourcing), sinon les 3 questions ; write-outreach garde ses gates durs — **CONVENTIONS = surface partagée, ack Rémi pending** |
| 0.21.2 | suite scénario 2 — les deux findings restants | **#2** `rank.py` : `why_now` construit UNIQUEMENT depuis un signal frais (mult > context) — un compte au signal `context`/non-daté (ex. page carrière active) a désormais un `why_now` VIDE au lieu du « Recrute en ce moment » mensonger ; le score garde la contribution faible du context, write-outreach retombe sur le pain point (testé : Beelix context→vide, Trait'Tendance frais→gardé). **#3** wall-time : `elapsed_s` ajouté aux receipts JSON de `rank.py`/`jobs.py`/`news.py` (`firmo.py` streame, laissé) + doctrine CONVENTIONS §8 « les receipts reportent le temps de chaque génération » (demande field-test de Robin). **#4** `find-hiring-signal` : receipt Phase 4 renforcé (STATE le next step, jamais une question — dérive constatée : le run a fini par « tu veux que je lance l'enrichissement ? » malgré le contrat) + relaie `elapsed_s` |
| 0.21.1 | scénario 2 « hiring signals » run réel — le flux a tenu (find-hiring-signal + signal-person + rank-accounts, 0 crédit, l'agent a refusé d'inventer des « now »), MAIS un bug silencieux : `find-hiring-signal` committait ses `signals` SANS `company_id` (juste `company_name`) → `rank-accounts` a joint sur `company_id` et a orphelinisé les 7 comptes au signal frais le plus fort (ressortis no-signal, score 10) ; rattrapé à la main par backfill | **Root cause** : `find-hiring-signal` Phase 4 insère les companies, relit leurs `_id`, puis écrit `company_id` (+ `company_name`) sur chaque signals row (aligné sur signal-person). **Filet défensif** : `rank.py` joint par `company_id`, fallback nom non-ambigu si vide, et **le signale** (`linkedByName`/`orphanedSignals` dans le receipt + le SKILL le remonte) au lieu de dropper en silence — testé (signal orphelin récupéré par nom). Restent ouverts (non patchés ce tour) : #2 `why_now` surévalue les signaux `context`, #3 pas de wall-time dans les receipts |
| 0.21.0 | préparation scénario 2 « hiring signals » — la sonde `priority_score`/`why_now` n'avait pas de brique : c'est `rank-accounts` (roadmap §« To build » #2), jamais construite. Décision produit avec Robin : un vrai outil Python figé (pas de code généré à la volée), une boucle for déterministe, et le `why_now` doit être une ENTRÉE de write-outreach (sinon la colonne ne sert à rien) | **NEW brick rank-accounts** : `scripts/rank.py` (Mode A, une passe déterministe — agrège les `signals`, fusionne fit `tier` × signal frais le plus fort × fraîcheur + bonus volume → `priority_score`/100 + `priority_tier` now/week/nurture + `why_now` template, distress→cap ; poids dans `rank_spec.json`, les « trous », le modèle n'écrit aucun code) → commit `priority_*`/`why_now`/`ranked_at` en un `db.py modify` · write-outreach lit `why_now` en accroche prioritaire (généralise `hiring_angle`, fallback pain point si vide) · slot phase 3b dans playbook-outbound · bench fixture vert (fit+signal→now, no-signal→week why_now vide, signal périmé→nurture, détresse→cap 15 ; commit db.py OK) |
| 0.20.2 | scénario 1 « base propre + ICP + no-signal control » (workspace notes-de-frais-daf) — le flux a tenu (drift guardrail impeccable, sourcing gratuit, score auto-débusqué) mais 4 écarts : (a) le 1er `db.py add` a planté car `--db` placé APRÈS la sous-commande (argparse global-only), auto-corrigé ; (b) une mesure `score` jugée sur la seule étiquette secteur → jugements creux et incohérents (data/BI noté 10 vs 5) ; (c) comité d'achat à 3 personas montré mais un seul fichier persona persisté ; (d) récaps `find`/`score` finissant par une question (doctrine = statements) | `db.py` accepte `--db`/`--root` AVANT ou APRÈS la sous-commande (parents=[dbflags], defaults SUPPRESS ; testé les deux positions) + CONVENTIONS §5 le documente · `score` doctrine « juger sur un vrai signal, jamais une étiquette » (sinon `conditional` déterministe, ou enrichir la colonne descriptive puis re-scorer gratuit) · `score` récap se termine par un statement (§8) · `context-write` persiste un fichier persona par rôle du comité + `gtm-onboard` Phase 3 lui transmet tout le comité |
| 0.20.1 | ladder verification on BOTH workers — predicted to WIN on `worker_api`, it LOST (283s / 28 done — the worst worker_api run) and also lost on `claude -p` (473s / 41 done: beat the 720s broken ladder but still under single-shot RUN A's 369s). Root cause: with no cold-start there's no fixed per-row cost to amortise, so rungs only STACK timeouts on slow rows. The one useful piece — oversized page → `sonnet` recovery — fired for real (1 `haiku`-overflow row recovered in 16s) | CONVENTIONS §11 CORRECTED: escalation ladder DROPPED (loses on both workers); doctrine re-anchored on a calibrated SINGLE SHOT + one `too_long`→`sonnet` recovery pass; worker choice reframed as speed-vs-cost (`worker_api` faster everywhere but metered API credits + cap; `claude -p` slower but free/uncapped). Process lesson: don't enshrine a technique before a field test confirms it — the 0.20.0 ladder was premature, fixed here |

Full pipeline validated in the field at **0 credits** end to end:
sourcing (FullEnrich free preview) → firmographics (official API) →
one verified decision-maker per company (registry + free searches).

### Engine worker lanes — the perf study (0.18.0 → 0.20.1)

At ~500 rows the engine's web-research lane felt slow next to Clay. We
A/B-tested the engine on a real 50-site batch (workspace `gtmia-agent`) to see
where the time goes and which settings help. The terms below recur, so here they
are in plain language first — read them before the results.

**Terms.**
- **Row** — one unit of work: one company, one website to check.
- **Worker** — the process that handles ONE row. The engine runs several at
  once; `--workers N` = how many rows are worked in parallel.
- **`claude -p`** — the DEFAULT worker. For each row it boots a full Claude Code
  command-line program. Capable, but heavy and slow to start up.
- **Cold-start** — the seconds a worker wastes booting up before it can do any
  real work (~10-20 s for `claude -p`).
- **`worker_api.py`** — the lightweight worker we added. Instead of booting the
  CLI, it calls Anthropic's API directly, and the web browsing runs on
  Anthropic's servers — so on your machine it's just one small network call.
  Quick to start, but it spends Anthropic **API credits**, not the flat-rate
  subscription that `claude -p` uses.
- **`--tools web` / `--tools none`** — a row that DOES navigate the web (slow, a
  cost per page) vs one that only reasons over data already in the row (fast,
  cheap).
- **Timeout** — the maximum seconds a worker is allowed before we give up on
  that row and mark it failed.
- **A/B test** — run the same job twice changing exactly ONE thing, then compare.

**What the A/B tests showed** (same 50 sites, one yes/no web question, `haiku`):

| Method | Worker | `--workers` | Timeout | Wall time | Rows answered |
|---|---|---|---|---|---|
| Single shot A | `claude -p` | 12 | 120 s | 369 s | 42 / 50 |
| Single shot B | `claude -p` | 50 | 120 s | — | **0 / 50 (collapsed)** |
| Single shot C | `worker_api` | 30 | 60 s | **133 s** | 38 / 50 |
| Ladder | `claude -p` | 12 | 90→120 s | 473 s | 41 / 50 |
| Ladder | `worker_api` | 30 | 45→90 s | 283 s | 28 / 50 |

`worker_api` single-shot (133 s) is the fastest of all; both ladders lose.

- **More `claude -p` workers ≠ faster.** At 50, every worker timed out (0 done):
  `claude -p` is heavy and limited by the local machine's CPU, and 50 of them on
  one Mac oversubscribe it. Even 12 already show contention. The ceiling here is
  a LOCAL limit (~12-16), not a network one — which corrected an earlier wrong
  assumption in the doctrine.
- **The real per-row cost is the web navigation (~88 s), not the cold-start.** A
  single site on its own answers in ~23 s; the rest is page-fetching + contention.
- **The lightweight worker is how you actually parallelise.** `worker_api` held
  30 workers where `claude -p` died at 50, and ran ~2.8× faster — because the
  heavy work runs on Anthropic's servers, not the Mac. Its price: API credits (a
  ~50-row web run repeated a few times hit the account's usage cap).
- **The escalation ladder LOSES — on both workers (the surprise).** We tested a
  "timeout ladder": run everyone fast at a low timeout, then re-run ONLY the
  failures at a higher one. The engine targets failures precisely (proven — each
  rung re-runs only its own survivors), but the method itself loses. On
  `claude -p` (473 s) the cold-start means no rung is ever cheap. On `worker_api`
  (283 s — the WORST worker_api run) there is no cold-start to amortise, so
  splitting only STACKS timeouts on the slow rows: a slow site times out at rung 1
  AND at rung 2, burning both, where one wide shot would have finished it. The one
  piece worth keeping is the **too-long recovery**: a page too big for `haiku`'s
  200k context is re-run on `sonnet` (1M context) — it recovered a row every
  single-shot run had left failed.

**The modifications, in order.**
- **0.18.0** — raised the parallel-worker cap (10 → 20) and made web/agent rows
  default to `haiku` (Anthropic's fast, cheap model) instead of the CLI's heavier
  default. The two cheapest speed-and-cost wins.
- **0.19.0** — raised the cap to 50 and shipped **`worker_api.py`**, the
  lightweight worker (opt-in via the `BRICKS_WORKER_CMD` switch); the engine now
  hands each run's settings (model, web on/off, page budget) to it.
- **0.20.0** — added **`--no-retry-timeout`** (a timed-out row fails on the first
  attempt instead of retrying at the same timeout; the old retry stays the
  default, so existing runs are unchanged) and first wrote the worker-per-lane
  doctrine into `CONVENTIONS §11`.
- **0.20.1** — **corrected the doctrine after the ladder tests**: dropped the
  escalation ladder (it loses on both workers), kept only the too-long → `sonnet`
  recovery pass, and re-anchored §11 on a calibrated single shot. Process note:
  in 0.20.0 the ladder was written into the doctrine *before* it was
  field-proven — exactly what the field-test loop exists to catch. Fixed here.

**The doctrine in one line.** Always a calibrated **single shot**, never the
ladder. Choose the worker by BUDGET, not speed — `worker_api` is faster in every
case, but it spends API credits and can hit a usage cap; `claude -p` is slower but
free and uncapped on the subscription. So: speed + API budget → `worker_api` at
30+; big cheap volume → `claude -p` at ~12-16; no-web work → `worker_api`. The
timeout is the one number you can't guess — measure it on a small sample (~60-90 s
for a 3-page web question) — and add ONE `too long → sonnet` recovery pass only if
oversized pages show up.

_The perf investigation is closed: the ladder is rejected, the winner is a
calibrated single shot + optional too-long recovery, and the worker is a budget
choice. Any next engine-perf idea gets the same treatment — measured before it
enters the doctrine._

### To build — Robin (data in)

**Hackathon Track 1 (Acquisition) — the missing bricks.** The infra
already covers ~70% of Track 1 (find → enrich → signals → score →
plan-outreach → write-outreach). These four close the gaps and target
the judging criteria (esp. #3 "depth of external data, FullEnrich &
Sillage"). Format: IN → does → OUT · [mode].

1. **signal-sillage** — THE priority (hits criterion #3 "…& Sillage"
   directly — without it, we cap ~12/25 on external-data depth). · IN:
   `companies`/`contacts`. → `fetchers/sillage.py` (HTTP, Mode A, same
   shape as `fullenrich_people.py`) pulls Sillage intent signals per
   account, driven by `runner.py --action fetch`. → OUT: `signals` rows
   `kind='intent'` (+ `intent_score`, evidence). · [A/C]

2. ~~**rank-accounts**~~ — DONE (0.21.0). The pitch's brain ("the agent
   tells you WHO to call first and WHY"). Shipped as a FROZEN deterministic
   script (`scripts/rank.py`, one for-loop, zero model — not a `score`
   preset in the end: no fuzzy measure to judge, so a self-contained
   kernel is simpler and faster) fusing `tier` + every fresh `signals`
   row into `priority_score`/100 + `priority_tier` (now/week/nurture) +
   a `why_now` template; weights in `rank_spec.json` (the holes).
   `why_now` is now an INPUT of write-outreach. · [A]

3. **warm-intro** — the unique differentiator (no other team will have
   it). · IN: target `contacts` + the user's own LinkedIn export / team
   profiles (their consented data). → matches on shared employer, shared
   school (FullEnrich education/employment data), mutual connection. →
   OUT: `warm_path` ("both ex-Google", "HEC 2015", "via X"). Deep
   FullEnrich use → more criterion-#3 points. · [B/C]

4. **inbound-qualify** — the live wow ("paste an email → 10s → qualified,
   routed, reply drafted"). · IN: an inbound lead (email/domain). →
   instant FullEnrich enrich + `score` vs ICP + route (hot→call /
   warm→sequence / junk→drop) + reply draft. → OUT: qualified & routed
   lead, `messages` draft. A playbook composing existing bricks — little
   new code, huge in Q&A. · [B]

5. **write-outreach — phone lane (extend, don't fork).** Track 1 wants
   "email, LinkedIn, phone". write-outreach covers email + LinkedIn;
   add a `phone` channel that drafts a call script + talking points from
   the same fresh signals (numbers already come from FullEnrich enrich).
   → OUT: `messages` rows `channel='phone'` (script, not sent). · [B]

6. **find-maps** — source companies from Google Maps (local/SMB
   sourcing, the sibling of find-directory-scrape). · IN: a business
   category + geography ("plombiers à Lyon", "growth agencies in
   Austin"). → `fetchers/gmaps.py` (HTTP/Bright Data, Mode A/C via
   `runner.py --action fetch`) pulls Maps listings: name, domain,
   address, phone, rating, review count. → OUT: `companies` rows
   (`source=gmaps`, deduped on domain, name-checked when domain-less).
   Feeds enrich → score like any other sourcing brick. · [A/C]

> Considered & rejected: **enrich-company** — a standalone "enrich a company"
> brick would duplicate the generic `enrich` skill (any company column via
> FullEnrich / web content) plus `enrich-firmographics` (the structured
> subset). Rule 1 forbids the overlap. If international firmographics ever
> needs its own path, extend `enrich-firmographics`, don't fork a new brick.

### To build — Rémi (data out)

crm-import · crm-push · outreach-send (+ send-guard hook + workspace
permission allowlist).

**Hackathon Track 1 — for Rémi:** **cadence-ab** — "multi-channel cadences
that A/B test themselves". write-outreach already writes the sequences;
this adds N variants per step (tagged `variant`), then — once
outreach-send + reply capture exist — measures replies and promotes the
winner. Full loop needs the send/track infra (Rémi's data-out lane),
hence his. Demo-only slice: generate A/B variants + the rationale.

_Shipped since this list was written: gtm-onboard (guided interview),
score (kill gate + tiers), web-researcher + THE ENGINE,
find-company-people engine lane, rank-accounts (priority_score + why_now)._

### Thomas (10%)

Docs site live + a generator compiling every `BRICK.md` into the docs
catalog (reference pages that can never drift) · GitHub issues board (one
issue per brick, assign = claim) · demo script.

---

## 4. How the data flows — Python? session? agent?

This is the single most important thing to understand about Bricks. Every
brick does its per-row work in exactly ONE of three modes.

**Mode A — deterministic Python (zero model).** A plain script does the
work: HTTP calls to free/keyed APIs, parsing, dedup, scoring math. No LLM
token spent, and the raw data NEVER enters any context — it goes script →
staging file → database. Fast, cheap, reproducible, identical every run.
- Tools: `firmo.py` (French gov company API), `jobs.py` (France Travail /
  HelloWork / career pages), `news.py` (Google News RSS), `db.py` (the
  database door), the `score.py` kernel, `fetchers/fullenrich_people.py`
  (FullEnrich people-search HTTP API).

**Mode B — the session model (the conversation itself).** The main Claude
you talk to reads results and decides: it drives MCP tools (FullEnrich
search, Bright Data scrape), applies the verification rules, compiles the
prompts. Best for SMALL volumes (≲ 5–40 rows), judgement, and anything
conversational (adding two contacts by voice, a one-off question). The
catch: MCP results ride the context, so Mode B does NOT scale to thousands
of rows.

**Mode C — THE ENGINE (headless disposable agents, at volume).**
`runner.py` loops over rows in tranches; for each row it spawns ONE
throwaway agent (`researcher.py`, a `claude -p` worker with the Bright Data
MCP optional) that reads its row + its pages in ITS OWN disposable context
and returns a validated structured answer; `runner.py` writes results in
waves through `db.py`. The session model never sees a row or a scraped page
— only the final reconciled receipt. This is how per-row AI work reaches
5 000+ rows without rotting the context. Preview 10 → GO → mass;
`runner.py rollback` undoes a run; statuses are the checkpoint.

### The data-plane rule (why the modes matter)

Before any data enters the conversation, one test: **does the MODEL need to
READ it to decide something?**

- **No** → it never touches the context. It moves by FILE: a provider CSV
  export (FullEnrich `export_*`) → `staging/` → `db.py import-csv`, or a
  Python fetcher → staging → DB. (Mode A.)
- **Yes, small volume** → it enters, capped: 10-row previews,
  `select --limit`, ≤ 3 sample rows in receipts. (Mode B.)
- **Yes, at volume** → it enters a DISPOSABLE context, never the session's:
  engine workers (Mode C), or sponge subagents for in-session volume.

Everything else is bookkeeping: the database is the bus AND the checkpoint
(statuses `pending → running → done | not_found | failed` make every run
resumable, idempotent, never paid twice); `~/.bricks/env` self-loads the
keys (the front's ⚙ writes it, values masked); the front reads the DB live
so a column fills in the UI as its wave commits.

### How each data source moves (quick map)

| Source | Moves via | Mode | Rides context? |
|---|---|---|---|
| French company registry | `firmo.py` → staging → db | A | no |
| Job boards / career pages | `jobs.py` → staging → db | A | no |
| Company news (RSS) | `news.py` → staging → db | A | no |
| FullEnrich roster search (volume) | `fetchers/fullenrich_people.py` via runner | A/C | no |
| FullEnrich emails/phones (bulk) | `enrich_bulk` → `export_*` CSV → import | A | no |
| FullEnrich search (preview ≤10) | MCP, in session | B | yes (capped) |
| Bright Data page (one site, judged) | MCP, in session | B | yes |
| Bright Data pages (per-row, volume) | `researcher.py --tools web` (engine) | C | no (disposable) |
| Model-generated content (drafts, scores) | session or engine workers | B/C | it IS the output |

---

## 5. The complete brick catalog (24 skills)

Every capability is one `skills/<name>/SKILL.md`; its precise contract lives
in that skill's `BRICK.md`. Format below: **IN → what it does → OUT · [mode]**.

### Entry & workspace

**gtm-onboard** · IN: a vague first GTM ask ("je vends X à Y", or nothing).
→ Infers a falsifiable v1 ICP (infers first, questions only what it can't),
routes to `context-write` (+ `workspace` for a new project). → OUT:
`context/icp.md` + `offer.md` populated, workspace ready. · [B]

**context-write** · IN: one free-text ICP sentence (from onboard). → Parses
it into the exact ICP schema, updates without wiping existing fields. →
OUT: `context/icp.md`. Never called directly. · [B]

**workspace** · IN: a name/goal, or nothing (auto-resolution). →
`workspace.py` scaffolds `bricks/workspaces/<name>/` (context/, bricks.db,
staging/, memory/), sets the current workspace, shows the banner. → OUT: a
sealed per-client world. · [A]

**interface** · IN: nothing. → Launches `front/server.py` (local web UI over
the workspace DB; ⚙ button manages the engine's API keys in `~/.bricks/env`).
→ OUT: a clickable URL, live Clay-style table. · [A]

### Find — sourcing NEW companies / contacts

**find** · IN: an ICP / criteria. → FullEnrich search preview (10 + total
count) → CSV export at volume; Bright Data or built-in web for niche/local
commerce. → OUT: `companies` (or `contacts`) rows, deduped on domain/email.
· [B + A export]

**find-directory-scrape** · IN: a directory / exhibitor / listicle URL. →
Bright Data scrapes the listing pages (JS + anti-bot handled), extracts
entities, verifies live domains. → OUT: `companies` rows,
`source=directory:<host>`. · [B, sponge subagents at volume]

**find-lookalike** · IN: seed companies (`segment='seed'`, fed by CRM export
/ CSV / dictated list). → Reads what the winners share, sources similar
companies on the discriminating signal. → OUT: `companies`,
`source=lookalike:<seed>`. · [B]

**find-hiring-signal** · IN: offer + ICP compiled into a pain matrix. →
`jobs.py hunt` sweeps France Travail / HelloWork / career pages (free,
deterministic, agencies filtered, prescored /65); SERP escalation only for
ATS/LinkedIn lanes; judgement adds the /100 and the cut. → OUT: `companies`
(score ≥ 70) + one `signals` row each with a ready outreach angle. · [A
engine + B judgement]

**find-company-people** · IN: `companies` + a title pattern. → The roster
expander (MULTIPLE contacts/company, no stop-at-first-hit). At volume:
`runner.py --action fetch --fetcher fullenrich_people` — the FullEnrich HTTP
API in the loop, with a STRICT-SYNONYM title-wave cascade (rename the
person, never widen who is hunted: GTM engineer ≠ SDR), verified & unmasked
only. Session sweep is the no-key fallback. → OUT: several `contacts` per
company, deduped on `person_key`, thin rows relayed to person-profile. · [C
engine / B fallback]

### Enrich — fill columns on existing rows

**enrich** · IN: a table + which column + which source. → Contact/firmo data
via FullEnrich (`enrich_bulk` → CSV import at volume); web-content via
Bright Data (`scrape_batch`, §9 waves). → OUT: the column + its `X_status`.
· [B + A export, waves]

**enrich-firmographics** · IN: `companies` (name + locality hint). →
`firmo.py` batch-queries the official French API (free, 7 req/s, parallel
workers); Bright Data only disambiguates via legal pages. → OUT:
`employees, industry, naf, siren, city, executives, parent_company`. · [A]

**enrich-buying-committee** · IN: enriched `companies`. → Picks ONE target
type (decision-maker vs champion) from the ICP once, then a cheap-first
waterfall (registry → FullEnrich search → LinkedIn SERP → team page),
verified always, ONE person per company. → OUT: one `contacts` row/company
with `role_type`. · [B, waves/sponge at volume]

**enrich-person-profile** · IN: `contacts` missing identity (CRM/CSV
imports, manual adds). → Free-first waterfall (FullEnrich search → LinkedIn
SERP → team page), verified in-source or `not_found`, never guesses. → OUT:
`role, seniority, linkedin_url`. · [B, waves]

**web-researcher** · IN: ANY per-row question ("ont-ils un configurateur en
ligne ?", "trouve le tél du standard", "quelle forme juridique ?"). →
Compiles the question into `prompts/<slug>/instructions.md` ({{column}}
variables) + `schema.json` (fields → columns), then THE ENGINE runs one
disposable agent per row (web-connected `--tools web` or pure judgement
`--tools none`); preview 10 → GO → mass. → OUT: one or several new columns
(structured, Clay-style), each with evidence + status. · [C]

### Signals

**signal-person** · IN: known `contacts` (need `linkedin_url` / a resolvable
company). → Four cheap-first passes: job change (FullEnrich search, free),
recent posts (Bright Data, per-record), hiring (`jobs.py check`, free),
company news (`news.py`, free). → OUT: dated, evidence-backed `signals` rows
(`kind`, `freshness`, `evidence_url`); job-moves freeze the contact. · [A
engine + B judgement]

### Transform & score

**transform** · IN: an existing table + an instruction (dedupe, filter,
derive, split, merge, clean). → Deterministic rules first (SQL-able via
`db.py`); prefers new columns over destroyed data; kills via
`status='disqualified'`, never deletes silently. → OUT: modified/derived
rows or tables. · [B decides, A executes]

**score** · IN: rows + natural-language scoring rules. → Compiles rules into
`spec.json` ONCE; `materialize.py` judges the fuzzy measures in parallel
headless agents (checkpointed, never re-judged); `score.py` computes the
total purely. File-based — never touches the DB until a separate commit
step. → OUT: `score`, `tier`, `sc_*` decomposition, `killed` + reason. · [A
kernel + C judges]

**rank-accounts** · IN: `companies` (`tier`) + `signals` (hiring, news,
job-change, intent). → A frozen deterministic script (`scripts/rank.py`,
one for-loop, zero model): aggregates each account's signals, fuses fit ×
strongest-fresh-signal × freshness + volume bonus into `priority_score`,
assembles a `why_now` one-liner; weights in `rank_spec.json`. Commits via
`db.py`. → OUT: `priority_score`, `priority_tier` (now/week/nurture),
`why_now`, `why_now_url` — the sorted call-list; `why_now` feeds
write-outreach. · [A]

### Answer (no DB write)

**scan-mentions** · IN: a question about ONE company's site ("ont-ils des
clients dans la banque ?"). → Bright Data scans the site, answers directly
in the chat backed by evidence. → OUT: a short paragraph — no row written.
· [B]

### Strategy & write

**plan-outreach** · IN: enriched + scored base + phase-0 facts (deal size,
maturity, audience). → Reads the evidence and decides motion / channel mix
(LinkedIn / email / both) / cadence / per-tier treatment. → OUT:
`context/strategy.md` (user-confirmed) + `contacts.channel_plan`. · [B]

**write-outreach** · IN: `strategy.md` + each contact's persona + `voice.md`
+ fresh signals. → CPPC copywriting < 100 words, one question per message,
per `channel_plan`, in the contact's language; drafts only, never sends. →
OUT: `messages` rows (`status='draft'`). · [B]

### Playbooks — orchestrators (explicit dispatch, no re-deciding)

**playbook-outbound** · IN: a workspace. → Chains the bricks in fixed order
— complete evidence (enrich) → score → signals → plan-outreach →
write-outreach — with guards between phases and ONE chain GO; stops where
approval is human. → OUT: the whole base advanced, final receipt. · [orch]

**playbook-lookalike** · IN: best customers (CRM export / CSV / dictated).
→ Import seeds → enrich them with every available brick → find what the
winners share → source & filter similar companies on the discriminating
signal. → OUT: a lookalike prospect list. · [orch]

### Extra

**create-landing-page** · IN: workspace context (offer / ICP / personas). →
Generates a premium single-file HTML landing page from the context (no
interview), deploys it to Vercel via GitHub on a generic domain. → OUT: a
live URL. · [B + scripts]


---

## 6. Milestones

1. ~~Retest pass~~ — DONE: two field campaigns validated end to end
   (tech-startups, relance-devis-habitat), five product versions shipped
   from their findings.
2. ~~Score (kill gate + icp-fit)~~ — DONE (shipped: deterministic kernel
   + headless judges, tiers, kill → `disqualified`). ~~Onboard~~ — DONE
   (gtm-onboard, guided interview). ~~THE ENGINE~~ — DONE (runner +
   researcher + web-researcher + find-company-people fetch lane). Next
   real work: fold the formal score brick into playbook-outbound's loop,
   and field-run the engine's web lane at volume.
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
