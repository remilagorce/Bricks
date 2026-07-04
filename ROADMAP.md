# Bricks — roadmap

The reference plan. Read PROJECT.md for decisions already shipped, CLAUDE.md
for working rules.

## The target (final version)

Bricks is the open-source GTM engine: a Clay alternative where the user owns
the data (local SQLite per workspace) and the intelligence (their own Claude
subscription). Six layers:

1. **Bricks** (~43, granular) — independent plugins, one capability each,
   IN/OUT contract in BRICK.md expressed as columns + statuses. Star topology:
   bricks never call each other; handoff = WHERE clauses on the table.
2. **Core** (frozen contract) — schema, statuses, db.py (single write door),
   shared agents (web-researcher, copywriter, data-janitor), governance hooks.
3. **Workspaces** — 1 folder = 1 client = 1 sealed world (context/, bricks.db,
   .mcp.json, CLAUDE.md, permission allowlist). Physical context isolation;
   duplicate a workspace to A/B test offers.
4. **Orchestration** — the workspace session composes bricks on the fly from
   the user's ask (the differentiator vs Clay's fixed workflows) + named
   playbooks for recurring motions.
5. **Cockpit** (local app) — tabs = workspaces, Clay-style live table with
   per-cell statuses, chat panel, bottom tabs (Companies / Contacts /
   Sequences / Signals / Context), draft→approved validation queue. Spawns
   headless Claude Code sessions per workspace folder.
6. **Distribution** — `claude plugin marketplace add remilagorce/Bricks`,
   MkDocs site for humans, community brick marketplace later.

Iron rules at every phase: data flows through the database, never the
conversation; paid actions confirm volume first; nothing leaves the machine
without a human (draft → approved is a human act).

## Phases

| Phase | Content | Status |
|---|---|---|
| V0 — steel thread | core + 4 bricks (find-fullenrich, enrich-website, enrich-email, write-sequence), fixed columns, manual chaining, demo workspace validated | DONE (branch `v0-first-bricks`) |
| V1 — hackathon | family coverage (~15 bricks), scoring + kill rules, onboard bricks, CRM basics, shared agents extracted, send guard hook, read-only table viewer if time | IN PROGRESS |
| V2 | cockpit app (tabs, live table, validation queue), playbooks, real sending (throttled, approved-only), dynamic column registry (columns/cells) | — |
| V3 — product | desktop packaging, public marketplace, community bricks, Sillage real-time signals + scheduled wake-ups | — |

## V1 split — Robin (IN side) / Rémi (OUT side) / Thomas (docs)

One brick = one branch = one PR = one person. Core changes = PR approved by
both Robin and Rémi.

### Together first (half a day, then core is frozen again)

- Single core PR: add the V1 family columns to schema.sql, scoring.yaml
  support, extract shared agents (web-researcher, copywriter), add the
  PreToolUse send-guard hook.

### Robin — data in

| Brick | IN → OUT |
|---|---|
| find-directory-scrape | directory URL → + companies |
| find-crm-lookalike | won-customers seed table → + lookalike companies |
| enrich-company-firmographics | domain → headcount, industry, country (Pappers for FR) |
| enrich-buying-committee | company + personas → + people with champion/decision-maker roles |
| enrich-person-profile | name + company → title, seniority, LinkedIn URL |
| signal-sillage-sync + signal-ingest | qualified accounts → live signal rows (if Sillage access) |
| maintenance of V0 bricks | find-fullenrich, enrich-website, enrich-email |

### Rémi — data out

| Brick | IN → OUT |
|---|---|
| score-killer-gate | cheap columns + scoring.yaml kill rules → status disqualified (early-stop) |
| score-icp-fit | enriched columns + scoring.yaml → score 0-100, tier, reasons |
| onboard-interview | dialogue → offer.md, icp.md |
| onboard-scoring-rules | ICP + won customers → scoring.yaml |
| write-icebreaker | pitch/news/activity → personalized opener column |
| crm-connect | credentials → workspace .mcp.json + field mapping |
| crm-best-customers | CRM → won-customers seed (feeds Robin's lookalike) |
| crm-push | qualified lead → account + contact created, crm_id column |
| outreach-mailbox-setup | mailbox credentials → send config + quotas |
| outreach-send | approved drafts → sent (throttled, guarded by hook) |

### Thomas — 10%

- MkDocs site live; generator that compiles BRICK.md files into the docs
  reference catalog (docs stay true automatically).
- GitHub Issues board: one issue per brick, assignee = claim.
- Fixtures QA + the hackathon demo script.
- Cockpit later (V2).

## Next steps (in order)

1. Robin: push `v0-first-bricks` (gh auth login, git push), open the PR.
2. PR review with Rémi — two decisions inside: fate of the placeholder `find`
   plugin (family router vs removal), schema validated as frozen contract.
3. Rémi + Thomas install: `claude plugin marketplace add remilagorce/Bricks`
   (or local clone) + `claude plugin install core@bricks …`.
4. 30-minute team meeting: merge the core V1 PR scope, open the V1 issues,
   everyone claims their first brick.
5. First new bricks: Robin → find-directory-scrape (free, demo-friendly);
   Rémi → score-killer-gate + score-icp-fit (unlocks early-stop, pure script).
6. Milestone demo: full pipeline with early-stop scoring on a real ICP —
   find → enrich → kill/score → emails → sequences, table telling the story.
