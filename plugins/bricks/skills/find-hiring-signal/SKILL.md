---
name: find-hiring-signal
description: Source NEW companies from their job postings — find who is hiring for the pain the offer solves. Use when the user says "trouve les boîtes qui recrutent un X", "qui embauche des Y en ce moment", "source sur signal recrutement", "hiring signals", "les entreprises qui viennent de poster une offre". Pain-matrix queries over ATS pages, LinkedIn Jobs, Indeed, France Travail via Bright Data; extracts and verifies offers, scores companies /100, commits only strong signals — each with a ready outreach angle.
---

# Find by hiring signal

**Before anything, read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`.**

You are not searching job ads — you are searching companies that just
revealed a business priority in public. A company hiring the role your
offer equips (or replaces) is a warm account with a dated, quotable
proof attached. This brick SOURCES new `companies` rows from that
signal; checking whether ALREADY-TRACKED companies hire is
`/bricks:signal-person`'s pass 3 (same doctrine, opposite direction).

Context gate (§3): the pain matrix derives from `context/offer.md` +
`context/icp.md`. TODO placeholders → infer an announced v1 from the
goal/request when the substance is there (don't stall the hunt behind
an interview); hand off to `/bricks:gtm-onboard` only when it is not.
Bright Data is the preferred engine; when it is down, the free channel
(built-in web search + page fetch) carries the run — field-tested at
equal quality during a full outage. The brick refuses to run only when
BOTH channels are unavailable. FullEnrich is not needed here.

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

**Below the big-spend threshold (§7, default 50 credits) the run does
not ask at all**: the matrix + budget + cut (RELATIVE — computed by
curate.py in Phase 2+3: commit ≥ 65 % of the points REACHABLE for this
ICP, park 45-65 %; announce the rule, the receipt shows the measured
numbers) are ANNOUNCED and the hunt proceeds — a wrong matrix costs ~0
with jobs.py, and the user adjusts after the receipt. Above the
threshold: ONE grouped GO for everything (field-tested: 5-6 serial
gates per run is what makes it slow). It returns to the user only if
reality invalidates the plan (absurd score distribution, an unplanned
paid step). A chain GO (follow-on bricks named by the user in the same
request) folds their budget lines into this same plan — zero mid-chain
confirmations, every receipt ends with statements, never questions, and
a downstream brick's HARD gate is never overridden: satisfy it at plan
time or end the chain before that brick, saying what is missing.
Persist to `memory/state.json` (`hiring_matrix`) + one
`memory/NOTES.md` line (§8); re-runs reuse it silently and re-ask only
if `context/` changed.

**Self-healing exclusions — two levels.** (1) Workspace: when compiling
the matrix, fold the workspace's kill flags into it — every intermediary
unmasked by ANY brick downstream (`/bricks:signal-person`,
`/bricks:enrich`, a manual kill) is recorded in `memory/` (state.json
kill flags / NOTES.md); read them and append those employer names to the
matrix's `exclude_employers`. (2) **Plugin — the cumulative memory**: an
opaque-brand cabinet that the employer-identity wave WEB-VERIFIED
belongs in `tools/providers/jobs.py` `KNOWN_STAFFING_BRANDS` — say so in
the receipt so the field-test loop appends it (workspace learning
evaporates on every fresh workspace; Voluntae was re-verified three runs
in a row before this list existed). A cabinet that fooled one run must
never reach a second one, whatever it is called, whatever the industry,
whatever the workspace.

## Phase 1 — the hunt (script first, SERP as escalation)

**Step 1 — `tools/providers/jobs.py hunt`: free, deterministic,
seconds.** Write the confirmed matrix to a temp JSON and run:

    python3 "${CLAUDE_PLUGIN_ROOT}/tools/providers/jobs.py" hunt \
      --matrix <matrix.json> --out bricks/tmp/hiring-<date>

The script generates the queries mechanically, fetches France Travail
and HelloWork search pages politely (plus offer detail pages for
microdata dates). **Size `--max-queries` upfront: ≥ titles × locations
× boards** — the default 30 truncates a 6-titles × 5-zones matrix
mid-sweep (field-tested: a run silently skipped its 3 terrain titles
and had to re-hunt, doubling the fetch time). `--max-details 40`
stays. The script flags agencies/stage/expired into `rejected.jsonl`,
matches tools/pains, pre-scores the mechanical 65/100 and aggregates
`companies.jsonl` — 0 credits, no LLM tokens. For SMB/artisan ICPs this
alone usually covers the market (field-tested: it reproduced the manual
Gironde run — 104 raw offers, 24 agencies flagged, MORICEAU's double
offer caught by the volume bonus — in under a minute).

**Step 2 — SERP escalation, ONLY for lanes the script cannot reach**
(tech/scaleup ICPs behind JS or anti-bot): ATS-direct domains
(`greenhouse.io`, `jobs.lever.co`, `ashbyhq.com`, `workable.com`,
`teamtailor.com`, `smartrecruiters.com`, `welcometothejungle.com`),
`site:linkedin.com/jobs` + `web_data_linkedin_job_listings`, Indeed.
All queries of the escalation go out as ONE `search_engine_batch` call
(and page reads as ONE `scrape_batch`), never serial queries. Budget
fixed at the phase-0 announcement (§7), ~1 credit per query/page;
1-credit health control first — Bright Data empty (29/29 on a field
run) → built-in web search carries these lanes too. NO date operators
anywhere (field-tested useless); freshness is read on the offer pages —
no date readable on the page → the offer is kept only as `context`,
never `fresh`. LinkedIn note: a public post's date derives from its
post ID.

## Phase 2+3 — curate: the FROZEN crible (a script, never session code)

jobs.py's staging is filtered, scored and angled by the frozen kernel —
NEVER by an ad-hoc script written in session and NEVER by judging rows
one by one in the conversation (field-tested: a run re-derived this
crible live, hit a case-sensitivity bug that wrongly rejected 105 valid
finance roles, and spent ~25 minutes debugging what the kernel does in
milliseconds):

    python3 "${CLAUDE_PLUGIN_ROOT}/skills/find-hiring-signal/scripts/curate.py" run \
      --staging <hunt outdir> --matrix <matrix.json> --out <rundir>

(For step-2 SERP hits, extract the same fields into the staging jsonl
first — curate runs over everything.) One deterministic pass, receipt
with `elapsed_s`:

- **Filters**: staffing/cabinets by NAME (`jobs.py` NAME_AGENCY_TOKENS +
  KNOWN_STAFFING_BRANDS — "… RECRUTEMENT", expertise comptable…),
  public/nonprofit employers (matrix `exclude_public`, default true),
  obvious mega groups (+ matrix `exclude_employers`),
  employer-name-is-a-job-title parsing artifacts, and everything jobs.py
  already flagged (agencies, stage, expired).
- **Role points**: +25 finance / +15 force terrain, matched case- and
  accent-insensitively; matrix `role_groups` overrides titles, points
  and angle templates per group.
- **The RELATIVE cut, MEASURED on the batch** — never an absolute 70.
  Some grid criteria are structurally out of reach: size (10) is never
  visible in an ad; the volume bonus (15) rewards big employers (an
  independent SME hires ONE chef comptable); tool mentions (15) almost
  never appear on France Travail/HelloWork cards (measured 1/144).
  curate computes `reachable` = 100 − the criteria the batch cannot
  produce, then **commit ≥ 65 % of reachable, park 45-65 %** — the
  receipt shows reachable/cut/park and which criteria were dropped. A
  multi-offer scaleup hunt keeps reachable high → the bar stays high
  automatically.
- **The outreach angle**, templated per role group with the offer's
  pains merged in (contextual proof, never "j'ai vu que vous recrutez").

Grid /100 unchanged: recency 20 · role 25 · tool 15 · pain 15 · volume
15 · size 10 (size stays for `/bricks:score`, post-enrichment). **The
volume bonus BOOSTS `hiring_score` but never gates the cut**: the
commit/park decision runs on a volume-free gate score (field-tested:
multi-offer cabinets and mega distributors trusted the committed band
while every single-offer target SME landed just under the cut — the
sort was inverted; volume stays where it belongs, as a priority signal
for `/bricks:rank-accounts` downstream).

**The employer-identity wave — the industry-proof net, BEFORE commit.**
Name tokens and offer-text patterns catch most intermediaries, but a
cabinet with an opaque brand and neutral prose can pass any static
filter (field-tested: 13 of 18 committed rows of a run were
modern-brand cabinets — Voluntae, Lynx RH, "super recruteur"… — and
cleaning them DOWNSTREAM cost 11 serial web checks). So before the DB
commit, verify the committed rows' identity in ONE parallel web wave
(all searches fired in a single message, built-in web search, free;
cap ~20 — above that, verify the top 20 by score and say so): one query
per company — is this an OPERATING company, or a recruiting / interim /
expertise-comptable intermediary? Kill the intermediaries from the
payloads (they join `rejected.jsonl` with the reason), THEN commit.
Bounded and upstream beats unbounded and downstream.

YOUR judgment beyond that wave stays by exception: read the receipt
(distribution, rejectReasons, samples), spot-check edge rows of
`committed.jsonl` against their `url`, and override individual calls —
re-add a wrongly rejected company by hand — never rewrite the crible's
logic in session. Return to the user ONLY if the distribution looks
absurd (everything under the park band, or > 90 % passing).
Company-level data only — never store candidate or recruiter personal
data (CNIL). This score is the brick's sourcing filter, not the ICP
score — `/bricks:score` still runs on these rows like any other.

## Phase 4 — commit and hand over

Four commands, all payloads pre-built by curate and piped from files
(§1, §4 — ONE write per phase, never per row):

```bash
# 1. companies (curate wrote the payload: name, source='hiring-signal',
#    status='new', location, hiring_score, hiring_angle)
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" add companies \
  --rows - --key name < <rundir>/companies_payload.json
# 2. read the _ids back
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" select companies \
  --cols _id,name --limit -1 > <rundir>/sel.json
# 3. build the signals rows — company_id ALWAYS set (emit-signals ERRORS
#    on any unmatched name rather than writing an orphan: field-tested,
#    orphaned signals broke rank-accounts' fit×signal fusion)
python3 "${CLAUDE_PLUGIN_ROOT}/skills/find-hiring-signal/scripts/curate.py" emit-signals \
  --committed <rundir>/committed.jsonl --ids <rundir>/sel.json \
  --out <rundir>/signals_payload.json
# 4. signals, deduped on the shared key convention
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" add signals \
  --rows - --key sig_key < <rundir>/signals_payload.json
```

`sig_key` = `hiring:<company_id>:<normalized evidence_url>` (scheme and
`www.` stripped, no trailing slash) — the SAME convention as
`/bricks:signal-person`, so both hiring writers key one offer
identically (field-tested: two conventions once coexisted and broke
cross-run dedup). Career-page evidence keys on the domain alone (one
hiring signal per company); board offers keep their full offer URL.
Boards carry no domain — companies dedup on `name` at insert, then on
`domain` once enrichment resolves it (domains verified, never guessed;
domain-less rows are name-checked like `/bricks:find-directory-scrape`).
Pre-existing companies get the signal added, never a duplicate row.

**The angle doctrine**: `hiring_angle` uses the offer as contextual
proof, never as a creepy opener — "vous structurez votre équipe RevOps
autour de HubSpot et du lead routing…", NOT "j'ai vu que vous
recrutez". `/bricks:write-outreach` picks it up as-is.

Receipt: "X companies committed (score ≥ <computed cut>), Y parked in
staging (park band), Z rejected (top reasons). Credits: A queries + B
pages, en `elapsed_s` (relayé depuis le receipt de jobs.py)." Max 3
sample rows. Then STATE the next step, never ASK it (field-tested
drift: this receipt shipped ending with "tu veux que je lance
l'enrichissement ?"): "Prochaine étape :
`/bricks:enrich-firmographics` → `/bricks:score` →
`/bricks:enrich-buying-committee` → `/bricks:write-outreach` (l'angle
est prêt) — dis le mot." A statement the user can act on or redirect,
not a question that stalls the chain.

## Volume mode

Subagents per query batch (≤ 10 parallel), writing to the run dir ONLY
(subagents never touch the database); the main thread verifies, dedups,
scores and commits via `db.py`. The single upfront budget covers the
whole run — subagents never spend beyond it.
