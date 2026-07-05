---
name: signal-person
description: Detect fresh outreach signals on known contacts — job changes (free), company hiring, recent LinkedIn posts, company news. Use when the user says "check les signaux", "quoi de neuf chez mes contacts", "qui a changé de poste", "est-ce qu'ils recrutent en ce moment", "est-ce qu'ils ont posté récemment", "surveille ces comptes", "signaux". Re-runnable scan writing dated, evidence-backed signal rows — fresh (≤60 days) signals are icebreaker material, older ones are context; tier-gated once scoring exists.
---

# Signal person

The dynamic sibling of enrich-person-profile: the profile is the photo,
signals are the movie. Scans KNOWN contacts and writes dated,
evidence-backed rows to a `signals` table: `job_change` (free, via
FullEnrich), `new_post` (LinkedIn posts, per-record), `hiring`
(LinkedIn job listings, per-record), `company_news` (SERP).
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
can force a full re-scan). Claim `running` via `db-writer` (absolute db
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
- **Pass 3 — hiring (Bright Data `web_data_linkedin_job_listings`, pro
  tools, per-record cost)**: PAID — explicit confirmation first (§8):
  one lookup per company of the in-scope contacts, hard cap 25
  companies per run. A company actively hiring is often the strongest
  intent signal of the four (growth, full order book, budget to
  spend). Signal `hiring`: the open roles in one line ("hiring 2
  poseurs + 1 conducteur de travaux"), `evidence_url` = the listing
  URL, `date` = the posting date. Tool absent from the tool list →
  pass unavailable; it ships with plugin ≥ 0.4.0 + Bright Data
  connected.
- **Pass 4 — company news (Bright Data `search_engine`, ~1 credit per
  query)**: batched queries `"<company>" + news terms relevant to the
  offer` (levée, acquisition, ouverture…), restricted to
  the last month, one query per company of the in-scope contacts.
  Signal `company_news` with the article URL. Announce query volume at
  scale (§8).

**Verification rule**: a signal without a source (FullEnrich record or
URL) does not exist — never infer activity, never date-guess. All passes
ran and nothing found → `signal_status='not_found'` (a result, not an
error).

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
`<kind>:<contact_id or company_id>:<url or new-company>`,
`status='new'`, `detected_at`. On the contact: `last_signal` (one
short human line for the table view), `signal_status`,
`signal_checked_at`; on a company change additionally `left_company=1`
(pass 1).

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
