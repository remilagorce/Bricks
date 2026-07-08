---
name: find-company-people
description: Expand companies into their full matching roster — MULTIPLE verified contacts per company from a title pattern. Use when the user says "ratisse les contacts", "trouve tous les profils X chez mes comptes", "liste les personnes de ces entreprises", "multi-thread ces comptes", "find company people". Cost-ordered waterfall WITHOUT stop-at-first-hit (FullEnrich search free → registry → LinkedIn SERP → team page), per-company cap, verified or skipped — the opposite end from enrich-buying-committee, which picks ONE opinionated target.
---

# Find company people

**Before anything, read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`.**

Expands a company into its matching ROSTER. `/bricks:enrich-buying-committee`
answers "who is THE door?" — one person, chosen by the targeting plan,
stop at first verified hit. This brick answers "who works there that
matches this profile?" — SEVERAL rows per company, same waterfall, no
stop. Use it for multi-threading (several stakeholders per account),
for reviving accounts whose single thread died (no reply, breakup
done, `left_company`), and for mid-size companies where a deal is
collective.

Scope: `companies` with `people_status` NULL or `pending`, never
disqualified rows; when a `tier` column exists, default to tier A/B.
FullEnrich is the main free engine: if `FULLENRICH_API_KEY` is absent,
say so — the brick still runs on the other rungs but most rosters will
cost credits instead of nothing.

If the user NAMES a company that is not in base, add it
(`source='user'`, receipt-flagged, ICP mismatch noted) and sweep it —
the explicit name IS the confirmation; never stop to ask (field-tested
friction: the run paused on "Doctrine n'existe pas, comment procéder ?"
when the intent was obvious).

## Phase 0 — the plan (autonomous by default)

Derive and present the plan in a single block (§7: announce the scope,
then run; ONE grouped GO only when real credits are engaged):

- **Title pattern** — from the user's words, else from
  `context/icp.md` (Buying roles) + `personas/` (e.g. gérant ·
  adjoint·e de direction · conducteur de travaux · assistant·e
  ADV/devis), in the companies' language.
- **Cap per company** — default 4 (the user can raise it).
- **Scope** — how many companies, which exclusions applied.
- **Worst-case budget** — "N companies could need the SERP rung: up to
  N × 2 queries ≈ X credits; most should resolve free via FullEnrich".
- **Chain GO** — when the user's request names follow-on steps in the
  same breath ("ratisse PUIS complète les profils PUIS les emails"),
  the plan includes one budget line per follow-on brick and THIS single
  GO authorizes the whole chain: zero confirmations between bricks,
  receipts flow one after the other, and only an UNPLANNED cost may
  come back to the user. A chain GO never overrides a downstream
  brick's HARD gate (e.g. `/bricks:write-outreach` refuses on an empty
  offer.md): the gate's requirement is either satisfied AT PLAN TIME or
  the chain ENDS before that brick, saying what is missing —
  field-tested: a "GO sec" produced 21 placeholder drafts a brick's
  contract forbids.

## The engine lane — volume via the API (preferred when `FULLENRICH_API_KEY` is set)

At volume this brick does not sweep in session — it compiles ONCE and
dispatches THE ENGINE (§5), FullEnrich's HTTP API doing the per-company
work deterministically:

1. **Compile the params JSON** (`bricks/tmp/people-<date>/params.json`)
   from the user's words + `context/icp.md` Buying roles — the ONLY
   judgment of the run, and where the intelligence lives:
   - **`title_waves` = strict synonyms of the SAME activity**, tightest
     first: `[["gtm growth engineer", "growth engineer"], ["head of
     growth", "growth lead"], ["growth marketer"]]`. A wave renames the
     person, it NEVER changes who is hunted — "GTM growth engineer" may
     cascade to "growth marketer", never to "SDR" (different activity,
     different pain).
   - Several roles named by the user = several GROUPS, each with its
     own waves, its own seniority codes (`Owner`, `Founder`, `C-level`,
     `VP`, `Head`, `Director`, `Manager`) and its own cap — never one
     mixed soup.
   - Show the compiled params in 5-6 lines, confirm ONCE, persist —
     re-runs reuse the file silently.
2. **Run through the iron gate (§5)** — preview first, then the mass:
   ```
   export FULLENRICH_PARAMS=bricks/tmp/people-<date>/params.json
   export FULLENRICH_OUT_TABLE=contacts
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/runner.py" --table companies \
     --step "${CLAUDE_PLUGIN_ROOT}/tools/providers/fullenrich.py:step" \
     --status-col people_status
   ```
   Preview: the found people appear in each `preview_row` (nothing
   written). ONE GO → same command `--commit`: verified unmasked
   contacts are inserted as child rows in `contacts` (dedup
   `linkedin_url`), `people_found`/`people_evidence` land on the
   company row, statuses are the checkpoint (re-run resumes pending).
   Per company the step stops at the FIRST wave with verified hits
   (precision: waves are fallback vocabulary, not net-widening). The
   evidence carries the observed credits — real cost, shown at preview,
   before the mass is authorized.
3. **No API key** (`~/.bricks/env`) → this lane is unavailable: say so
   once, point to `~/.bricks/env`, and fall back to the session sweep.

## The sweep — in waves, cheap first, NO stop at first hit

For small scopes (≲5 companies stay in-session, §5 exempt) or when the
API key is absent. Run each rung as ONE wave across every company still
under its cap — all of a wave's calls fire in parallel in a single
message (`search_engine_batch`, `scrape_batch`, one batched
`firmo.py --stdin`):

- **A. FullEnrich people search (free — searches cost 0 credits)**:
  `current_company_domains` × the title patterns. Keep every result
  whose CURRENT employment matches our company and whose title matches
  the pattern. **Masked-name rule**: a masked name ("Hakim A.") is
  NEVER inserted (unusable for email enrichment, unverifiable
  downstream) — keep it aside; if a later rung resolves the full name,
  insert with that proof; otherwise mention it in the receipt.
- **A-bis. Registry executives (free, official)** — one batched
  `tools/providers/firmo.py --stdin` call per wave: the registry's
  gérant / président / DG are the roster's core at artisan/SMB size,
  with FULL first names (field-tested: 7 of 19 contacts came from the
  registry after SERP and scrape returned nothing). Skip people
  already in base.
- **B. LinkedIn SERP (Bright Data `search_engine`, ~1 credit, max 2
  queries/company)** — only when rung A returned fewer than the cap:
  `site:linkedin.com/in "<title>" "<company>"`, indexed snippets only,
  never logged-in pages. Accept when the snippet shows the person
  CURRENTLY in a matching role at that company.
- **C. Team/about page (Bright Data scrape or free fetch, ~1 credit)**
  — names + roles published by the company itself; exact matches only.

**Verification rule (all rungs)**: name + role + company must cohere
in the source itself. Ambiguity → skip the person (not the company).
Nothing verifiable anywhere → `people_status='not_found'` — a result,
never an invention.

## Dedup, cap, and existing rows

Same person from two sources → ONE row, best evidence kept. A person
ALREADY in `contacts` (e.g. the gérant `/bricks:enrich-buying-committee`
inserted) is never duplicated — the brick completes the roster AROUND
them, and never touches their `role_type` (that column belongs to the
committee's doctrine). More matches than the cap → keep the closest to
the pattern (title fit, then seniority), name the runners-up in the
receipt. Dedup key: (company_id + full_name), email as secondary when
present.

## Writes (batched, via db.py — §4)

`contacts` rows: `company_id` + `company_name` (denormalized — humans
read this table), `full_name`, `role` (verbatim title), `linkedin_url`
when the source gave it, `source` = `fullenrich-search` |
`registry` | `linkedin-serp` | `team-page`, `status='new'`; init
`profile_status='pending'` on rows missing seniority or linkedin_url so
`/bricks:enrich-person-profile` completes them — bus relay, never a
call. Then `companies.people_status='done'`. One `db.py` write per
batch of 5-8 companies, never per row.

## Receipt

"X contacts added across Y companies (avg Z/company): A via FullEnrich
(free), B via registry (free), C via SERP (~C credits). N companies
not_found. M masked profiles not inserted. Existing contacts untouched:
[names]." Max 3 sample rows. **The receipt ENDS the run — statements,
never questions.** "Next: `/bricks:enrich-person-profile` → `/bricks:enrich`
(emails) → `/bricks:write-outreach` — dis le mot et je lance."
