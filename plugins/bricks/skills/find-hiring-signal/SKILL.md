---
name: find-hiring-signal
description: Source NEW companies from their job postings — find who is hiring for the pain the offer solves. Use when the user says "trouve les boîtes qui recrutent un X", "qui embauche des Y en ce moment", "source sur signal recrutement", "hiring signals", "les entreprises qui viennent de poster une offre". Pain-matrix queries over ATS pages, LinkedIn Jobs, Indeed, France Travail via Bright Data; extracts and verifies offers, scores companies /100, commits only strong signals — each with a ready outreach angle.
---

# Find by hiring signal

You are not searching job ads — you are searching companies that just
revealed a business priority in public. A company hiring the role your
offer equips (or replaces) is a warm account with a dated, quotable
proof attached. This brick SOURCES new `companies` rows from that
signal; checking whether ALREADY-TRACKED companies hire is
signal-person's pass 3 (same doctrine, opposite direction). Contract
in this directory's BRICK.md.

## Before anything

Follow `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` §2 and §3 — HARD context
gate here (like write-sequence): the pain matrix derives from
`context/offer.md` + `context/icp.md`; if they are TODO placeholders,
stop and fill them first. Bright Data is the preferred engine; when
it is down, the free channel (built-in web search + page fetch)
carries the run — field-tested at equal quality during a full outage.
FullEnrich is not needed by this brick.

## Phase 0 — the pain matrix (once per workspace, user-confirmed)

Derive from offer + ICP and present in ≤ 8 lines:

- **Titles**: the roles a company hires when it handles your pain
  manually (that hire IS the signal).
- **Tools**: stack/competitor names whose mention marks a fit.
- **Pain words**: the vocabulary of the problem inside a posting
  (workflow, manual process, surcroît d'activité…).
- **Geo + exclusions**: countries/cities; recruitment agencies & ESN,
  stage/alternance, company sizes the ICP kills.
- **Negative keywords, IN the queries**: staffing brands and interim
  wording (`-intérim -"agence d'emploi" -Adecco -Manpower -Randstad
  -"Aquila RH"`…) — field-tested: ~135 of ~150 raw offers were agency
  noise; kill it upstream, not post-hoc.

Every query encodes ONE GTM hypothesis —
`"<title>" "<tool>" "<pain>" "<geo>" site:<source>` — never
`"startup jobs France"`. Show 3 example queries with the matrix.

**ONE GO covers the whole run**: matrix + phase-1 budget + the commit
cut (default ≥ 70, 50-69 parked in staging) are confirmed in a SINGLE
question — after that GO the run goes to the end without re-asking
(field-tested: 5-6 serial gates per run is what makes it slow). It
returns to the user only if reality invalidates the plan (absurd
score distribution, an unplanned paid step). Persist to
`memory/state.json` (`hiring_matrix`) + one NOTES.md line; re-runs
reuse it silently and re-ask only if `context/` changed.

## Phase 1 — the hunt (script first, SERP as escalation)

**Step 1 — `tools/jobs.py hunt`: free, deterministic, seconds.** Write
the confirmed matrix to a temp JSON and run:

    python3 "${CLAUDE_PLUGIN_ROOT}/tools/jobs.py" hunt \
      --matrix <matrix.json> --out <workspace>/staging/hiring-<date>

The script generates the queries mechanically, fetches France Travail
and HelloWork search pages politely (plus offer detail pages for
microdata dates, caps `--max-queries 30 --max-details 40`), flags
agencies/stage/expired into `rejected.jsonl`, matches tools/pains,
pre-scores the mechanical 65/100 and aggregates `companies.jsonl` —
0 credits, no LLM tokens. For SMB/artisan ICPs this alone usually
covers the market (field-tested: it reproduced the manual Gironde run
— 104 raw offers, 24 agencies flagged, MORICEAU's double offer caught
by the volume bonus — in under a minute).

**Step 2 — SERP escalation, ONLY for lanes the script cannot reach**
(tech/scaleup ICPs behind JS or anti-bot): ATS-direct domains
(`greenhouse.io`, `jobs.lever.co`, `ashbyhq.com`, `workable.com`,
`teamtailor.com`, `smartrecruiters.com`, `welcometothejungle.com`),
`site:linkedin.com/jobs` + `web_data_linkedin_job_listings`, Indeed.
Budget fixed at the phase-0 GO (§8); 1-credit health control first —
Bright Data empty (29/29 on a field run) → built-in web search
carries these lanes too. NO date operators anywhere (field-tested
useless); freshness is read on the offer pages. LinkedIn note: a
public post's date derives from its post ID.

## Phase 2 — extract and verify (staging, never straight to db)

The script's `offers.jsonl` arrives pre-extracted and pre-filtered —
read it and apply JUDGMENT only: spot-check top rows against their
`url`, catch what keyword matching misread (an agency phrasing the
script missed, a pain word used in another sense). For step-2 SERP
hits, scrape (`scrape_as_markdown`) and extract the same fields into
the same staging files. Keep ONLY offers that pass every filter
(the script enforces the mechanical ones; re-check edge cases):

- posted ≤ 60 days (≤ 30 preferred — say which);
- employer clearly identifiable — recruitment agencies/ESN excluded
  unless the end client is named (then the client is the row);
- not stage/alternance (unless the user asked);
- description substantial enough to extract tools/pain from.

Company-level data only — never store candidate or recruiter personal
data (CNIL).

## Phase 3 — group and score (the GTM logic, not the scraping)

The script already grouped by company (`companies.jsonl`) and scored
the mechanical 65: recency (20), tool mention (15), pain wording
(15), ≥2 offers volume (15). Add the judgment points — role squarely
in the offer's category (25), size fits the ICP when visible (10) —
and adjust where keyword matching misread context. Full grid /100:

| Criterion | Points |
|---|---:|
| freshest offer ≤ 7 days | 20 |
| role squarely in the offer's category | 25 |
| target/competitor tool named | 15 |
| explicit pain wording in the description | 15 |
| ≥ 2 relevant offers within 60 days | 15 |
| company size fits the ICP (when visible) | 10 |

The cut was declared at the phase-0 GO (default: commit ≥ 70, park
50-69 in staging). Apply it and show the distribution (≥ 70 / 50-69 /
< 50) in the receipt; return to the user ONLY if it looks absurd
(everything < 50, or > 90 % passing). This score is the brick's
sourcing filter, not the ICP score — the score brick still runs on
these rows like on any other.

## Phase 4 — commit and hand over

Via `db-writer` (absolute db path): `companies` rows — `name`,
`domain` (verified on the offer or the company site, never guessed;
domain-less rows are name-checked like find-directory-scrape),
`source='hiring-signal'`, `status='new'`, `hiring_score`,
`hiring_angle` — dedup on domain, existing rows enriched with the
signal instead of duplicated. Plus ONE `signals` row per company:
`kind='hiring'`, `date` = freshest offer, `freshness` (≤ 60 days =
`fresh`), summary = roles + pains + volume, `evidence_url`, `sig_key`
= `hiring:<company_id or name>:<normalized evidence_url>` with
`--key sig_key` — URL normalized (scheme and `www.` stripped, no
trailing slash), the SAME convention as signal-person: both hiring
writers must key one offer identically or cross-run dedup breaks
(field-tested: a backfill and a live run produced two conventions).
Career-page evidence keys on the domain alone (one hiring signal per
company); board offers keep their full offer URL. Commits
go in ONE `db-writer` dispatch per phase — the staging file, batched
— never one dispatch per row.

**The angle doctrine**: `hiring_angle` uses the offer as contextual
proof, never as a creepy opener — "vous structurez votre équipe RevOps
autour de HubSpot et du lead routing…", NOT "j'ai vu que vous
recrutez". write-sequence picks it up as-is.

Receipt: "X companies committed (score ≥ 70), Y parked in staging
(50-69), Z rejected (top reasons). Credits: A queries + B pages." Max
3 sample rows. Next steps: enrich-firmographics → score →
enrich-buying-committee → write-sequence (the angle is ready).

## Volume mode

Subagents per query batch (≤ 10 parallel), writing to staging ONLY;
the main thread verifies, dedups, scores and commits via `db-writer`.
The single upfront budget covers the whole run — subagents never
spend beyond it.
