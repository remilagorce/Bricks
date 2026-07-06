---
name: find-company-people
description: Expand companies into their full matching roster — MULTIPLE verified contacts per company from a title pattern. Use when the user says "ratisse les contacts", "trouve tous les profils X chez mes comptes", "liste les personnes de ces entreprises", "multi-thread ces comptes", "find company people". Cost-ordered waterfall WITHOUT stop-at-first-hit (FullEnrich search free → LinkedIn SERP → team page), per-company cap, verified or skipped — the opposite end from enrich-buying-committee, which picks ONE opinionated target.
---

# Find company people

Expands a company into its matching ROSTER. enrich-buying-committee
answers "who is THE door?" — one person, chosen by the targeting plan,
stop at first verified hit. This brick answers "who works there that
matches this profile?" — SEVERAL rows per company, same waterfall, no
stop. Use it for multi-threading (several stakeholders per account),
for reviving accounts whose single thread died (no reply, breakup
done, `left_company`), and for mid-size companies where a deal is
collective. Contract in this directory's BRICK.md.

## Before anything

Follow `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` §2 and §3. Scope:
`companies` with `people_status='pending'`, never disqualified rows,
never kill-rule-flagged ones (flags in `memory/NOTES.md` /
`state.json` count as out of scope until the score brick's verdicts
are in base — 0.4.1 doctrine); when a `tier` column exists, default
to tier A/B. FullEnrich (§4) is the main free engine: if
disconnected, say so — the brick still runs on rungs B/C but most
rosters will cost credits instead of nothing.

If the user NAMES a company that is not in base, add it
(`source='user'`, receipt-flagged, ICP mismatch noted) and sweep it —
the explicit name IS the confirmation; never stop to ask
(field-tested friction: the run paused on "Doctrine n'existe pas,
comment procéder ?" when the intent was obvious).

## Phase 0 — the plan (autonomous by default)

Derive and present the plan in a single block. §8 decides what happens
next: total worst case below the big-spend threshold (default 50
credits) → **announce and RUN, no question asked**; above it → ONE
grouped GO for the whole batch, fallbacks included. The plan block:

- **Title pattern** — from the user's words, else from
  `context/icp.md` (Buying roles) + `personas/` (e.g. gérant ·
  adjoint·e de direction · conducteur de travaux · assistant·e
  ADV/devis), in the companies' language.
- **Cap per company** — default 4 (the user can raise it).
- **Scope** — how many companies, which exclusions applied.
- **Worst-case budget** — "N companies could need rung B: up to
  N × 2 SERP queries ≈ X credits; most should resolve free via
  FullEnrich". Below the big-spend threshold the whole plan runs
  without any confirmation — announced, then receipts; the run returns
  to the user only if reality exceeds what was announced (§8).
- **Chain GO** — when the user's request names follow-on steps in the
  same breath ("ratisse PUIS complète les profils PUIS les emails" /
  "jusqu'aux séquences, sans me redemander"), the plan includes one
  budget line per follow-on brick and THIS single GO authorizes the
  whole chain: zero confirmations between bricks, receipts flow one
  after the other, and only an UNPLANNED cost (outside the announced
  budgets) may come back to the user. A chain GO never overrides a
  downstream brick's HARD gate (e.g. write-outreach refuses on an
  empty offer.md): the gate's requirement is either satisfied AT PLAN
  TIME (ask for the missing input inside the single GO) or the chain
  ENDS before that brick and the receipt says exactly what is missing
  — field-tested: a "GO sec" produced 21 placeholder drafts a brick's
  contract forbids.

## The engine lane — volume via the API (preferred when `FULLENRICH_API_KEY` is set)

At volume this brick does not sweep in session — it compiles ONCE and
dispatches the engine (CONVENTIONS §11), FullEnrich's HTTP API doing the
per-company work deterministically:

1. **Compile `prompts/people/params.json`** from the user's words +
   `context/icp.md` Buying roles — the ONLY judgment of the run, and
   where the intelligence lives:
   - **`title_waves` = strict synonyms of the SAME activity**, tightest
     first: `[["gtm growth engineer", "growth engineer"], ["head of
     growth", "growth lead"], ["growth marketer"]]`. A wave renames the
     person, it NEVER changes who is hunted — "GTM growth engineer" may
     cascade to "growth marketer", never to "SDR" (different activity,
     different pain). The cascade exists because real titles rarely
     match the user's words; the boundary is the activity itself.
   - Several roles named by the user ("des SDR ET des growth engineers
     ET des CEO") = several GROUPS, each with its own waves, its own
     seniority codes (`Owner`, `Founder`, `C-level`, `VP`, `Head`,
     `Director`, `Manager`) and its own cap — never one mixed soup.
   - Show the compiled params in 5-6 lines, confirm ONCE, persist —
     re-runs reuse the file silently.
2. **Run** — preview first, then the mass:
   `runner.py run --action fetch --fetcher fullenrich_people --params …
   --out-table contacts --run-id people-<date> --preview 10` → the user
   checks the interface → ONE GO → `--commit`. Per company the fetcher
   stops at the FIRST wave with verified hits (precision: waves are
   fallback vocabulary, not net-widening); verified unmasked contacts
   are inserted deduped on `person_key`, thin rows relayed to
   enrich-person-profile (`profile_status='pending'`), everything
   tagged `source_run` (rollback removes the inserted contacts too).
   `metadata.credits` flows into the receipt — the preview shows the
   REAL observed cost before the mass is authorized (§8 with facts).
3. **No API key** (`FULLENRICH_API_KEY`, via `~/.bricks/env` or a shell
   export — §11) → this lane is unavailable: say so once, point to
   `~/.bricks/env`, and fall back to the session sweep below.

## The sweep — in waves (§9), cheap first, NO stop at first hit

Run each rung as ONE wave across every company still under its cap —
all of a wave's calls fire in parallel in a single message, and the
batch tool variants carry it when several companies need the same rung
(`search_engine_batch` for rung B, `scrape_batch` for rung C, one
batched `firmo.py --stdin` for A-bis). A company only leaves the sweep
when its cap is reached or every rung has run:

- **A. FullEnrich people search (free — searches cost 0 credits)**:
  `current_company_domains` (or names) × the title patterns,
  `max_per_company` = cap. Keep every result whose CURRENT employment
  matches our company and whose title matches the pattern. Take
  full_name, exact title → `role`, seniority, linkedin_url.
  **Masked-name rule**: FullEnrich sometimes masks last names
  ("Hakim A."). A masked name is NEVER inserted (unusable for email
  enrichment, unverifiable downstream) — keep it aside; if rung B/C
  resolves the full name, insert with that proof; otherwise mention
  it in the receipt ("1 more profile exists, name withheld by the
  source").
- **A-bis. Registry executives (free, official)** — one batched
  `tools/firmo.py` call per company still under the cap: the
  registry's gérant / président / DG are the roster's core at
  artisan/SMB size, with FULL first names — it resolves the
  "M. Miller" initial-only cases company sites publish (field-tested:
  7 of 19 contacts came from the registry after SERP and scrape
  returned nothing). Skip people already in base.
  **Before any PAID rung, read the workspace memory**: a documented
  Bright Data outage routes rungs B/C to the free channel (built-in
  search + fetch) directly — field-tested: 14 SERP + 5 scrapes ran
  into a KNOWN-dead channel before the note was read.
- **B. LinkedIn SERP (Bright Data `search_engine`, ~1 credit, max 2
  queries/company)** — only when rung A returned fewer than the cap:
  `site:linkedin.com/in "<title>" "<company>"`, indexed snippets
  only, never logged-in pages. Accept when the snippet shows the
  person CURRENTLY in a matching role at that company.
- **C. Team/about page (Bright Data scrape or free fetch, ~1
  credit)** — names + roles published by the company itself; exact
  matches only.

**Verification rule (all rungs)**: name + role + company must cohere
in the source itself. Ambiguity → skip the person (not the company).
Nothing verifiable anywhere → `people_status='not_found'` — a result,
never an invention.

## Dedup, cap, and existing rows

Same person from two sources → ONE row, best evidence kept. A person
ALREADY in `contacts` (e.g. the gérant enrich-buying-committee
inserted) is never duplicated — the brick completes the roster AROUND
them, and never touches their `role_type` (that column belongs to the
committee's doctrine). More matches than the cap → keep the closest
to the pattern (title fit, then seniority), name the runners-up in
the receipt. Dedup key: (company_id + full_name), email as secondary
when present.

## Writes (batched, via db.py — §5, pass `--db <absolute path>`)

`contacts` rows: `company_id` + `company_name` (denormalized —
humans read this table), `full_name`, `role` (verbatim title),
`linkedin_url` when the source gave it, `source` =
`fullenrich-search` | `linkedin-serp` | `team-page`,
`status='new'`; init `profile_status='pending'` on rows missing
seniority or linkedin_url so enrich-person-profile completes them —
bus relay, never a call. Then `companies.people_status='done'`. One
`db.py` write per batch of 5-8 companies, never per row.

## Volume mode

The engine lane above IS the volume mode when the API key is present —
tranches, parallel fetches, preview, rollback, all inherited from
`runner.py`. Without the key: up to ~40 companies, the main thread's
parallel waves are the fast path — no subagents (§9.5); beyond ~40,
batches of 5-8 per subagent (up to 10 parallel), findings appended to
`staging/people-<date>/candidates.jsonl`, main thread verifies,
dedups and commits via `db.py`. The phase-0 budget covers the
whole run.

## Close the run

`memory/state.json` (counts per rung), one NOTES.md line, receipt:
"X contacts added across Y companies (avg Z/company): A via
FullEnrich (free), B via SERP (~B credits), C via team pages. N
companies not_found. M masked profiles not inserted. Existing
contacts untouched: [names]." Max 3 sample rows. Next steps:
enrich-person-profile (complete thin rows) → enrich (emails) →
write-outreach — each contact gets ITS persona, never the same email
twice into one company.

**The receipt ENDS the run — statements, never questions.** Name the
natural next step as a statement ("Next: enrich-person-profile — dis
le mot et je lance"), never "veux-tu que… ?". One GO bought a
finished run, not a dialogue (field-tested friction: two trailing
questions per receipt).
