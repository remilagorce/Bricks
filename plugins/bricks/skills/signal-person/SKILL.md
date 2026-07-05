---
name: signal-person
description: Detect fresh outreach signals on known contacts — job changes (free), company hiring, recent LinkedIn posts, company news. Use when the user says "check les signaux", "quoi de neuf chez mes contacts", "qui a changé de poste", "est-ce qu'ils recrutent en ce moment", "est-ce qu'ils ont posté récemment", "surveille ces comptes", "signaux". Re-runnable scan writing dated, evidence-backed signal rows — fresh (≤60 days) signals are icebreaker material, older ones are context; tier-gated once scoring exists.
---

# Signal person

The dynamic sibling of enrich-person-profile: the profile is the photo,
signals are the movie. Scans KNOWN contacts and writes dated,
evidence-backed rows to a `signals` table: `job_change` (free, via
FullEnrich), `new_post` (LinkedIn posts, per-record), `hiring`
(segment-aware multi-source job sweep), `company_news` (SERP).
Account-level product signals (usage spikes, Sillage) belong to
signal-sillage — this brick covers public signals around the tracked
people and their companies. Contract in this directory's BRICK.md.

## Before anything

Follow `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` §2 and §3. Column relay:
contacts need `linkedin_url` for passes 1-2 (run enrich-person-profile
or enrich-buying-committee first) and a resolvable company for pass 3.
Scope: when a `tier` column exists (score brick), default to tier A/B
only; otherwise state the scope ("N contacts with a linkedin_url") and
confirm with the user before any PAID pass. Contacts of disqualified
companies are never scanned (§8.5) — and kill-rule flags recorded in
`memory/NOTES.md` / `state.json` exclude a company the same way until
the score brick ships. FullEnrich (§4) gates pass 1 only.

## Freshness semantics (what makes this brick re-runnable)

Rows enter scope when `signal_status='pending'` OR `signal_checked_at`
is older than 7 days (the skill re-inits those to `pending`; the user
can force a full re-scan). The window applies PER PASS:
`memory/state.json` logs which passes each scan ran, and a pass that
never ran on a row is always due — one pass's stamp never blocks
another (field-tested: a morning job-change scan must not mute an
afternoon hiring sweep). Claim `running` via `db-writer` (absolute db
path). Every scanned row gets `signal_checked_at` stamped, found or not.
Signals are append-only, deduped on `sig_key` — re-runs never duplicate
a signal already seen.

## The passes (cheap first; each announced, each optional)

- **Pass 1 — job change (FullEnrich search, FREE — searches cost 0
  credits)**: look each contact up by `person_linkedin_urls` (fallback:
  full_name + company). Compare the returned CURRENT employment against
  our stored `role` + company. Two outcomes, handled DIFFERENTLY:
  - **Company change (move)** → signal `job_change` ("was <role> at
    <old> · now <title> at <new company> since <date>") + set
    `left_company=1` and `last_signal` on the contact, then STOP
    touching that row: its identity columns stay FROZEN — they describe
    who the person was at THIS company, and rewriting them makes the
    table lie (field-tested: the Julia Levy fixture ended up "Account
    manager @ PREDICTICE"). Never reset `profile_status` on a move. The
    receipt says: thread dead at the old account, warm door open at the
    new one — following the person there is the USER's call
    (enrich-buying-committee on that company if it is in scope).
  - **Promotion (same company)** → signal `job_change` ("promoted to
    <title>") + reset `profile_status='pending'`: the row stays
    anchored to the same company, so letting enrich-person-profile
    refresh role/seniority is legitimate — bus relay, never a call.
  Person absent from FullEnrich → no verdict (absence of data is not a
  signal).
- **Pass 2 — recent posts (Bright Data `web_data_linkedin_posts`, pro
  tools, per-record cost)**: PAID — explicit confirmation first (§8):
  "N contacts × 1 record", hard cap 25 per run. Pull the contact's
  recent public posts, keep those newer than `signal_checked_at` (first
  scan: last 30 days). Signal `new_post`: the topic in one line + the
  angle it offers against `context/offer.md`, `evidence_url` = the post
  URL. Tool absent from the tool list → pass unavailable; tell the user
  it ships with plugin ≥ 0.4.0 (update + restart), never emulate it by
  scraping profile pages (login wall).
- **Pass 3 — hiring (script first — 0 credits for most rows)**: a
  company actively hiring is often the strongest intent signal of the
  four (growth, full order book, budget to spend). Run the engine:

      python3 "${CLAUDE_PLUGIN_ROOT}/tools/jobs.py" check \
        --companies <batch.json> --keywords "<trade terms from ICP>" \
        --out <workspace>/staging/signals-<date>

  one JSON row per company (`company_id`, name, domain, location).
  The script sweeps France Travail by trade keyword ONCE for the
  whole batch (FT matches employer names poorly — field-tested: that
  sweep is what finds them), checks each company by name, probes
  career pages on known domains, and returns per-company verdicts
  (`hiring` / `quiet`) with dated, sourced offers — seconds,
  0 credits, agencies pre-flagged. Escalate to Bright Data ONLY for
  companies the script cannot see (tech/scaleup on ATS or LinkedIn
  Jobs: ATS-direct SERP + `web_data_linkedin_job_listings`; budget
  announced §8, cap 25 companies, 1-credit health control first —
  outage → built-in web search carries the lane). NEVER date
  operators in queries.
  Every hit is VERIFIED by reading the offer page
  (`scrape_as_markdown`): the employer must be OUR company —
  recruitment agencies/ESN posting for unnamed clients are excluded,
  stage/alternance excluded by default — and the posted date must be
  readable. Signal `hiring`: open roles + what the offer reveals
  (tools, pain wording — "recrute 2 poseurs, surcroît d'activité"),
  `date` = posting date, `evidence_url` = the offer URL. Several
  relevant offers ≤ 60 days → say so in the summary (volume = stronger
  signal). Company-level data only — never store candidate or
  recruiter personal data (CNIL).
- **Pass 4 — company news (`tools/news.py`, free)**: run

      python3 "${CLAUDE_PLUGIN_ROOT}/tools/news.py" \
        --companies <batch.json> --out <workspace>/staging/news-<date>

  Google News RSS — one fetch per company, 0 credits, last-month
  window (`--days`): dated items with outlet, `term_hits` (offer
  vocabulary, override with `--terms`) and a `warning` flag on
  distress vocabulary (redressement, liquidation — kill-gate
  material, NEVER an icebreaker). The script filters mechanically;
  the LLM judges RELEVANCE — homonyms are the trap (`name_in_title`
  helps, the call is judgment; an article about someone else's DUPIN
  is not a signal). Signal `company_news` with the article URL. SERP
  escalation only when RSS is quiet AND the account is tier A
  (announced, §8).

**Verification rule**: a signal without a source (FullEnrich record or
URL) does not exist — never infer activity, never date-guess. All passes
ran and nothing found → `signal_status='not_found'` (a result, not an
error).

**Downgrade rule**: `not_found` is only legal when the signals table
holds NO valid row for that contact/company. A re-scan that finds
nothing NEW on a row with existing signals closes `done` — the scan
happened, the signals on file stand (field-tested: a free re-scan
wrongly downgraded three contacts carrying valid context signals).

**Signal age — the 60-day rule**: every signal carries its own `date`
and a `freshness` verdict computed at detection: ≤ 60 days old =
`fresh` — icebreaker material ("congratulations on the new role" still
lands); older = `context` — useful background on the account, but
never presented as news (the fixture's 9-month-old move congratulated
as fresh is exactly the bot-smell we refuse). Downstream consumers
(write-sequence) re-check `date` at write time; `freshness` is the
at-detection verdict that makes the split visible in the table.

## Writes (immediately, per contact)

`signals` table via `db-writer` (`--key sig_key`): `contact_id` +
`contact_name` (person-level kinds; empty for company-level ones),
`company_id`, `company_name` (denormalized — the table is read by
humans), `kind` = `job_change` | `new_post` | `hiring` |
`company_news`, `date` (the signal's own date), `freshness` = `fresh`
(≤ 60 days) | `context`, `summary` (1-2 lines, anchored in the
evidence), `evidence_url`, `source` = `fullenrich-search` |
`linkedin-posts` | `linkedin-jobs` | `news-serp`, `sig_key` =
`<kind>:<contact_id or company_id>:<url or new-company>` (URLs
normalized — scheme and `www.` stripped, no trailing slash — the same
convention as find-hiring-signal, so both hiring writers key one
offer identically; EXCEPTION: `hiring` evidence from a company's OWN
career page keys on the domain alone, `hiring:<company_id>:<domain>` —
a career-page mention is one signal per company whichever page
carries it, field-tested dup: homepage vs deep page made two keys for
the same hiring; board offers keep their full offer URL — distinct
offers are distinct signals),
`status='new'`, `detected_at`. On the contact: `last_signal` (one
short human line for the table view), `signal_status`,
`signal_checked_at`; on a company change additionally `left_company=1`
(pass 1). At volume, group writes in batches of 5-8 through staging
(§6) — one `db-writer` dispatch per batch, never one per row: the
per-row dispatch overhead is what makes runs feel slow.

## Volume mode

More than 10 contacts: batches of 5-8 per subagent, up to 10 in
parallel; subagents append raw findings to
`staging/signals-<date>/raw.jsonl`; the main thread verifies (source URL
present, dates sane, dedup) and commits via `db-writer`. Paid passes
announced before launching, per pass (§8).

## Close the run

`memory/state.json` (counts per kind, credits/records spent), one
`NOTES.md` line, receipt: "Signals: X job changes (F fresh / C
context), Y hiring, Z posts, W news items. N contacts quiet
(not_found). Moves: [names] — rows frozen (`left_company=1`),
follow-up at the new company is your call. FRESH signals are
icebreaker material — run write-sequence on those contacts next." Max 3
sample rows. Cadence: on-demand today; a scheduled `claude -p "check les
signaux"` run is the natural next step (same pattern as signal-sillage);
real-time is cockpit V2.
