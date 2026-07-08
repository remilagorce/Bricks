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

Follow `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` §2 and §3 — context gate:
the pain matrix derives from `context/offer.md` + `context/icp.md`. TODO
placeholders → apply §3: infer an announced v1 from the goal/request
when the substance is there (don't stall the hunt behind an interview),
ask the three quick questions only when it is not. Bright Data is the preferred engine; when
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

**Below the big-spend threshold (§8, default 50 credits) the run does
not ask at all**: the matrix + budget + cut (RELATIVE — see Phase 3:
commit ≥ 65 % of the points REACHABLE for this ICP, park 45-65 %;
announce the computed absolute numbers) are ANNOUNCED and the hunt
proceeds — a wrong
matrix costs ~0 with jobs.py, and the user adjusts after the receipt.
Above the threshold: ONE grouped GO for everything (field-tested: 5-6
serial gates per run is what makes it slow). It
returns to the user only if reality invalidates the plan (absurd
score distribution, an unplanned paid step). A chain GO (follow-on
bricks named by the user in the same request) folds their budget
lines into this same plan — zero mid-chain confirmations, every
receipt ends with statements, never questions, and a downstream
brick's HARD gate is never overridden: satisfy it at plan time or end
the chain before that brick, saying what is missing. Persist to
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
All queries of the escalation go out as ONE `search_engine_batch` call
(and page reads as ONE `scrape_batch`), never serial queries (§9).
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

**The cut is RELATIVE to the points reachable at sourcing — never an
absolute 70.** Two of the grid's criteria are structurally out of reach
on some ICPs: size (10) is never visible in a job ad (it is deferred to
enrichment), and the ≥2-offers volume bonus (15) rewards big employers —
an independent SME hires ONE chef comptable, not three. Field-tested
twice: with those 25 points unreachable the ceiling is ~60-75, an
absolute ≥ 70 commits (almost) nothing, and every run had to improvise a
~45-50 override. When the same override happens every run, the rule is
wrong — so the rule is now: compute `reachable` = 100 minus the criteria
this ICP cannot mechanically produce (size when unknown at sourcing;
volume bonus when the ICP is single-offer SMEs), then **commit ≥ 65 % of
reachable, park 45-65 %** (SMB example: reachable 75 → commit ≥ 49, park
34-49; a multi-offer scaleup hunt keeps reachable 90-100 → the bar stays
high automatically). Declare the computed absolute numbers at the
phase-0 GO. Apply it and show the distribution (commit / parked /
rejected) in the receipt; return to the user ONLY if it looks absurd
(everything below the park band, or > 90 % passing). This score is the
brick's sourcing filter, not the ICP score — the score brick still runs
on these rows like on any other.

## Phase 4 — commit and hand over

Via `db.py` (§5, pass `--db <absolute path>`): `companies` rows — `name`,
`domain` (verified on the offer or the company site, never guessed;
domain-less rows are name-checked like find-directory-scrape),
`source='hiring-signal'`, `status='new'`, `hiring_score`,
`hiring_angle` — dedup on domain, existing rows enriched with the
signal instead of duplicated. **Insert the companies FIRST, then read
their `_id` back** (`db.py select companies --cols _id,domain,name` on
the rows you just wrote) — because the signals rows MUST carry the
company's `_id`. Plus ONE `signals` row per company: **`company_id`**
(the `_id` just read back — never omit it: a signals row without
`company_id` is an orphan that downstream joins silently drop,
field-tested — it broke rank-accounts' fit×signal fusion) +
**`company_name`** (denormalized, for the human table view, same as
signal-person), `kind='hiring'`, `date` = freshest offer, `freshness`
(≤ 60 days = `fresh`), summary = roles + pains + volume,
`evidence_url`, `sig_key`
= `hiring:<company_id or name>:<normalized evidence_url>` with
`--key sig_key` — URL normalized (scheme and `www.` stripped, no
trailing slash), the SAME convention as signal-person: both hiring
writers must key one offer identically or cross-run dedup breaks
(field-tested: a backfill and a live run produced two conventions).
Career-page evidence keys on the domain alone (one hiring signal per
company); board offers keep their full offer URL. Commits
go in ONE `db.py` write per phase — the staging file, batched
— never one dispatch per row.

**The angle doctrine**: `hiring_angle` uses the offer as contextual
proof, never as a creepy opener — "vous structurez votre équipe RevOps
autour de HubSpot et du lead routing…", NOT "j'ai vu que vous
recrutez". write-outreach picks it up as-is.

Receipt: "X companies committed (score ≥ <computed cut>), Y parked in
staging (park band), Z rejected (top reasons). Credits: A queries + B
pages, en
`elapsed_s` (relayé depuis le receipt de jobs.py — §8 wall-time)." Max
3 sample rows. Then STATE the next step, never ASK it (§8, house rule
0.8.1 — field-tested drift: this receipt shipped ending with "tu veux
que je lance l'enrichissement ?"): "Prochaine étape :
enrich-firmographics → score → enrich-buying-committee → write-outreach
(l'angle est prêt) — dis le mot." A statement the user can act on or
redirect, not a question that stalls the chain.

## Volume mode

Subagents per query batch (≤ 10 parallel), writing to staging ONLY;
the main thread verifies, dedups, scores and commits via `db.py`.
The single upfront budget covers the whole run — subagents never
spend beyond it.
