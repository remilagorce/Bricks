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
| Bright Data + FullEnrich MCP wiring | Robin | ✅ shipped, both Connected |

### To build — Robin (data in)

enrich-firmographics · enrich-buying-committee · enrich-person-profile ·
signal-sillage

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

### To build — Robin (data in)

**enrich-firmographics**
- IN: `companies.domain`, `firmo_status='pending'`.
- OUT: `employees`, `industry`, `country`, `siren`, `executives` columns.
- Strategy: the French shortcut — fetch `/mentions-legales` (legally
  mandatory) → extract SIREN → Pappers API (script-grade call, free tier)
  returns headcount, NAF code, and the executives for free. Non-FR
  companies: agent estimation from site + LinkedIn, flagged as estimate.
  Cheap column → run it early, it feeds the kill gate AND
  enrich-buying-committee.

**enrich-buying-committee**
- IN: enriched company row + `context/icp.md` buying roles + personas.
- OUT: `contacts` rows (full_name, role champion|decision-maker,
  company_id).
- Strategy: size-based shortcut — small companies (his ICP): the
  decision-maker IS the gérant, already in `executives` from Pappers, zero
  cost. Larger: subagent web search on title patterns (site team page,
  public LinkedIn results). The textbook example of column relay:
  it reads what firmographics wrote, never calls it.

**enrich-person-profile**
- IN: `contacts` with full_name + company, `profile_status='pending'`.
- OUT: `role`, `seniority`, `linkedin_url` columns.
- Strategy: public SERP only (`site:linkedin.com/in "name" "company"`) —
  read the indexed snippet, never log into LinkedIn (ToS + burned
  accounts). Complement with team pages / press bios. `not_found` is an
  acceptable answer; never guess.

**signal-sillage**
- IN: qualified accounts (tier A/B once scoring exists).
- OUT: signal rows + companies flagged "wake up" for re-score/sequence.
- Strategy: step zero is the access spike (account, API key, docs). Then
  `sync` pushes the account list; `ingest` polls on demand or via a cron
  `claude -p` run (real-time webhook = cockpit, V2). Demo plan B: simulated
  signals in fixtures, clearly labeled.

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

1. **Retest pass** — full test script on the merged main (in progress,
   6 fixes already shipped from test #1).
2. **Score + onboard** (Rémi) and **firmographics + buying-committee**
   (Robin) — unlocks the early-stop demo moment: "it stops spending on
   its own".
3. **Full pipeline demo** on a real ICP: find → enrich → kill/score →
   contacts → emails → sequences, the table telling the story live.
4. **crm-import + playbook-lookalike** end-to-end (the differentiator vs
   Clay).
5. V2: cockpit (tabs UI), outreach-send with approval queue, Sillage
   real-time.
