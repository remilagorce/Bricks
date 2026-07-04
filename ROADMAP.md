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

find-directory-scrape — La skill reçoit une URL d'annuaire (liste d'exposants d'un salon, annuaire de créateurs, classement…). Un sous-agent reçoit la mission « extrais nom + site de chaque entreprise listée, suis la pagination » et upserte directement en base (dédup par domaine, source=directory:<site>). Deux pièges anticipés : les annuaires en JavaScript pur (la page arrive vide → la skill le détecte et le dit honnêtement, navigateur en V2) ; et les annuaires sans site web (→ passe 2 optionnelle : petite recherche web par nom pour retrouver le domaine, proposée à l'utilisateur car plus lente).

find-crm-lookalike — Point important : elle n'attendra pas le CRM de Rémi. La skill accepte trois sources de seed : la table clients-gagnés (quand crm-best-customers existera), un CSV, ou une liste dictée (« mes 5 meilleurs clients sont… »). L'agent déduit le pattern commun (secteur, taille, géo, style), le formule en 3-4 requêtes de similarité, et un sous-agent cherche 3 à 5 sosies par seed. Chaque candidat passe par l'upsert domaine — les doublons avec l'existant fusionnent tout seuls.

enrich-company-firmographics — L'astuce 100 % française : toute entreprise FR doit publier ses mentions légales → un script va chercher /mentions-legales et en sort le SIREN → appel API Pappers (script pur, pas d'agent) qui rend effectif, code NAF, pays… et les dirigeants, gratuitement. Fallback pour les non-FR : estimation par l'agent depuis site + LinkedIn, marquée comme estimation. Prérequis : les colonnes headcount/industry/country/siren dans la PR core, et une clé Pappers (quota gratuit).

enrich-buying-committee — Elle exploite un raccourci propre à ton ICP : dans une boutique de 1 à 10 personnes, le comité d'achat, c'est le gérant — et son nom est déjà dans la base si firmographics est passée avant (dirigeants Pappers). Donc : si size_hint est solo/small → insertion directe du dirigeant en décideur, coût zéro. Sinon, sous-agent avec les title patterns de context/personas (recherche web ciblée, page équipe du site) pour trouver champion + décideur. C'est le plus bel exemple du relais par colonnes : elle lit ce que firmographics a écrit, sans jamais l'appeler.

enrich-person-profile — Volontairement sans scraping LinkedIn connecté (ToS + comptes grillés) : on interroge les résultats de recherche publics (site:linkedin.com/in "prénom nom" "entreprise") et on lit le snippet indexé — titre, entreprise actuelle, URL du profil — complété par une bio presse ou page équipe si elle existe. Écrit title, linkedin_url, seniority (colonne core PR). not_found assumé quand la personne est introuvable : on ne devine jamais.

signal-sillage-sync + signal-ingest — Étape zéro avant d'écrire quoi que ce soit : le spike d'accès (avez-vous un compte Sillage, une clé, leurs docs ?). Ensuite sync = un script qui pousse les comptes tier A/B vers Sillage et note l'abonnement. ingest en V1 = du polling (on tire les nouveaux signaux à la demande ou via un cron claude -p, on écrit des lignes signaux + on marque les comptes « à réveiller ») — le webhook temps réel exige un serveur qui écoute, c'est le cockpit, V2. Plan B démo si pas d'accès à temps : signaux simulés dans les fixtures, clairement étiquetés, pour montrer la chaîne « levée détectée → re-score → séquence contextualisée ».

Maintenance des briques V0 — Trois chantiers concrets : (1) find-fullenrich : dès ton premier OAuth, confronter la skill à la réalité des tools MCP (leurs noms exacts, leurs champs) et ajuster les étapes ; (2) enrich-website : durcir — politique de retry, détection des pages vides/JS, le cas « Smallable » (en-têtes cassés) qui doit finir en failed propre ; puis la faire basculer sur l'agent partagé web-researcher quand la PR core l'aura extrait ; (3) enrich-email : un test payant sur 2-3 contacts réels pour valider l'écriture retour et les statuts, avant tout volume.

L'ordre que je te conseille (les dépendances le dictent) : find-directory-scrape d'abord (aucune dépendance, valeur démo immédiate) → enrich-company-firmographics (elle débloque les kill rules taille/pays de Rémi ET le nom du gérant) → enrich-buying-committee (s'appuie dessus) → enrich-person-profile → find-crm-lookalike (démarre au CSV sans attendre Rémi) → Sillage dès que l'accès est confirmé. La maintenance V0 se glisse en continu, au fil de ce que tes tests révèlent.

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
