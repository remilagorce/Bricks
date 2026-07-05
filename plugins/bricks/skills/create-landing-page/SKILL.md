---
name: create-landing-page
description: Génère une landing page HTML premium à partir du contexte workspace (offre, ICP, personas) — sans interview — puis la déploie sur Vercel (via GitHub) sur un domaine générique. "Crée une landing page", "landing pour mon offre", "page produit", "one-pager web", "déploie ma landing".
---

# Create landing page

Produces a single self-contained HTML landing page from the current
workspace's GTM context, then ships it live. Positioning, audience, tone,
and proof points come from `context/` — this brick assembles the brief,
executes [landing.md](landing.md) (embedded HTML generator,
MIT/alirezarezvani), and finishes by deploying the page to a generic
Vercel domain via GitHub, following [deploy.md](deploy.md).
Never writes to `bricks.db`.

## Before anything: resolve the workspace and read the context

Follow `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` §2 and §3:

1. `python3 "${CLAUDE_PLUGIN_ROOT}/tools/workspace.py" status` — init or
   switch as needed.
2. Read the current workspace's offer, ICP, and every file under
   personas/. Talk about their *content*, never their file names.
3. Apply the drift guardrail: if the user's request targets a different
   product or ICP than the workspace context, stop and resolve (switch /
   new workspace / update context) before generating.

## Autonomy rule — infer first, ask last

**Default: answer every intake question yourself from context.** Do not
run Phase 0 from `landing.md`. Pre-fill all four intake slots below,
then generate using the spec in `landing.md` with the brief already
complete.

Ask the user **only** when a slot stays empty after reading context +
the user's message — and only for that slot, one question maximum. If
still unknown after one question, infer with an explicit caveat (same
spirit as `landing.md`'s sparse-input fallback).

Never ask for information already in context or in the user's request.

## Context → brief mapping

Derive the brief from context before generating:

| Landing intake | Source (deduce, do not ask) |
|---|---|
| **Product + elevator pitch** | offer — what we sell, problems solved, proof points → 1–2 sentences |
| **Audience register** | ICP buying roles + target companies → (1) technical, (2) business, (3) consumers, (4) internal |
| **Brand overrides** | Tone of voice + any color hints in the request → HEX or `"default"` |
| **Tone** | Offer tone + audience → professional / playful / authoritative / minimal |

Also pull from context for copy (do not invent facts):

- **Hero headline / subtext** — from the one-sentence offer + ICP payoff
- **Feature bullets (3–6)** — from problems solved + proof points
- **CTA** — one low-friction action aligned with the offer
- **Social proof** — only explicit proof points; omit if none

If the offer is still TODO placeholders, **stop once**: offer the three
context-gate questions from CONVENTIONS §3. Do not generate generic
boilerplate on an empty offer.

## Generate — read landing.md, skip Phase 0

1. **Read** `${CLAUDE_PLUGIN_ROOT}/skills/create-landing-page/landing.md`
   in full — that file is the generation engine (HTML structure, GSAP,
   brand system, validation rules). Skip its Phase 0; your brief is final.
2. **Slug** — run:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/create-landing-page/scripts/kebab_slug_generator.py" \
     "<product name>" "<workspace>/landing-pages"
   ```
3. **Write** the HTML to `<workspace>/landing-pages/<slug>.html` (create
   the directory if missing). On duplicate slug, append a date suffix.
4. **Validate** — run:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/create-landing-page/scripts/html_validator.py" \
     --file "<workspace>/landing-pages/<slug>.html"
   ```
   If FAIL, fix only the failing sections in one pass — do not abandon
   the file. Flag any inferred copy with `<!-- inferred: … -->`.

Brief checklist (all fields filled from context before step 3):

```
Product: <name + elevator pitch>
Audience: <1|2|3|4 + rationale>
Brand: <HEX overrides or "default">
Tone: <professional|playful|authoritative|minimal>
Hero headline / subtext / features / CTA / proof
```

## Deploy — final step, read deploy.md

Once the HTML validates, deployment is the last step of every run — the
page is not "done" until it is live on a generic Vercel domain.

1. **Read** `${CLAUDE_PLUGIN_ROOT}/skills/create-landing-page/deploy.md`
   in full — it is the deployment engine (preflight → deploy → receipt),
   all driven by `scripts/deploy_landing.py`. Never run raw
   `git`/`gh`/`vercel` commands yourself.
2. **Preflight** (`--check`) verifies git, the GitHub CLI, the Vercel CLI
   and their credentials. If anything is missing, ask the user for
   exactly what the check names — install command, `! gh auth login`,
   `! vercel login`, or a Vercel token — then re-check. This is the one
   place where asking is expected: never deploy with fabricated or
   assumed credentials.
3. **Deploy** (`--deploy`) pushes the page to a (private by default)
   GitHub repo named `landing-<slug>`, then deploys it to Vercel
   production. The generic domain is `https://landing-<slug>.vercel.app`.

Skip deployment only if the user explicitly says not to deploy (e.g.
"juste le fichier HTML") — then note in the receipt that the page is
local-only and can be deployed later by re-invoking this skill.

## Receipt

Report in 4–7 lines: **production URL first**, then output path, GitHub
repo, audience + tone chosen, which context fields drove the copy,
validator result. Do not paste the full HTML or deploy logs.
Offer to tweak one section (a re-run redeploys the same URL).

## Close the run

Append one line to `memory/NOTES.md` (landing slug, audience, tone,
production URL). Update `memory/state.json` with
`{ "lastLandingPage": "<path>", "lastLandingDeploy": "<production URL>" }`
if the file exists; create minimal state otherwise.
