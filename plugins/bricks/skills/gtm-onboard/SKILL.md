---
name: gtm-onboard
family: core
description: Entry point and router for the modular GTM engine. Discovers a falsifiable v1 ICP by inferring first and questioning second, then hands the finished profile to context-write (and to workspace when a new one is needed). Use at the first GTM interaction on a project — "je veux lancer un GTM sur X", "aide-moi à définir mon ICP", "je vends Y à Z", "lance mon outbound", or an empty / vague opening. Trigger broadly: better to over-trigger onboarding than to miss it.
---

# GTM onboard

The front door of the Bricks GTM engine: a **router + ICP discovery** brick.
It does two things and stops. First it routes — it reads the current
workspace and decides whether to onboard here, modify an existing ICP, or
spin up a new workspace. Then it runs a discovery interview that produces
one falsifiable v1 ICP conforming to the schema.

It never writes the context itself. When the profile is filled and
challenged, it delegates:

- to **context-write** (sister skill, not user-invocable) to persist the ICP;
- to **workspace** (sister skill) when a brand-new workspace is warranted.

The ICP it produces is always a **v1 hypothesis**, never "the right ICP" —
downstream bricks (outreach, ads) are what raise its confidence.

## Before anything: read the conventions, then inspect the workspace

**First, always read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` in full** — this
is mandatory, not optional. It is the shared contract every brick obeys
(workspace resolution, the context gate, and the rule to never name context
files to the user). Do this before any other action in an onboarding.

Then follow §2: run
`python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/workspace.py" status`. Do NOT edit any
file here — the status output is the raw material for Phase 0's routing
decision. When a current workspace exists, read the offer and ICP context to
know what is already defined (talk about their content, never their file
names — CONVENTIONS §3).

## The four phases (run in order)

```
- [ ] Phase 0 — Routing: inspect context, pick case A/B/C/D
- [ ] Phase 1 — Discovery: infer first, question second, fill the schema
- [ ] Phase 2 — Challenge: falsify entreprise / persona / localisation
- [ ] Phase 3 — Handoff: call context-write with the ICP + mode + workspace id
```

## Phase 0 — Routing

Inspect the current workspace context, then match one case. Carry forward
the **mode** (`overwrite`/`append`) and any target ICP id — Phase 3 needs
them.

| Case | Situation | Action |
|---|---|---|
| **A** | Context empty | → Phase 1 (mode `append`, first ICP) |
| **B** | Context exists, project coherent with the input, no ICP defined | → Phase 1 (mode `append`) |
| **C** | Context exists, project coherent, one or more ICPs already defined | Ask: **"tu veux modifier l'ICP existant [nom/id], ou ajouter un nouvel ICP ?"** Store the choice as mode `overwrite` (+ target id) or `append`, pass it to Phase 3. If several ICPs exist, list them with their id so the user picks which to modify. → Phase 1 |
| **D** | Context exists, project **manifestly different** | Explicitly propose creating a **new workspace**. If yes → handoff to workspace, then Phase 1. If no → continue in the current workspace in mode `append`. |

**"Project manifestly different" criterion:** divergence on **at least two**
of the three dimensions {secteur, produit vendu, marché cible}. Formulate a
confirmation question — never decide unilaterally. Example: *"Ça ressemble
à un projet différent de ton workspace actuel (autre secteur, autre cible).
Je te crée un nouveau workspace dédié, ou on reste ici ?"*

**Workspace handoff (case D, user says yes).** Hand off to the `workspace`
skill to create a `new <name> --goal "..."`. Display the returned banner +
welcome line VERBATIM (CONVENTIONS §2), then resume at Phase 1 inside the
fresh workspace (mode `append`, first ICP).

## Phase 1 — Discovery

Goal: fill an ICP object conforming to the schema in
[references/icp_schema.md](references/icp_schema.md) — read it now. **Central
rule: infer first from the input and the context, question second.** Present
every inference as a hypothesis to confirm, not an open question.

- Do not ask what the input or the context already answers.
- Phrase inferences as *"je suppose X — confirme ou corrige"*, never
  *"quel est X ?"*.
- **One question per turn, maximum.**

**Stop condition:** discovery ends when every schema field is filled —
except `validated_by`, which stays `null`, and `confidence`, which stays
`"hypothèse"` on exit. Then go to Phase 2.

A rich input ("Je vends un SaaS de conformité RGPD aux cliniques privées en
France") should trigger massive inference and only a couple of confirmation
questions. A bare or vague input ("j'ai une idée de business") means you
drive: propose a concrete first hypothesis for each field and let the user
react to something rather than face a blank page.

## Phase 2 — Challenge falsifiable

Once the schema is full, pass it through a falsification round on three
dimensions. This is not cosmetic: if answers stay vague, **go back to
Phase 1 on the offending field** — never validate an empty answer. Question
banks (3-4 per dimension) live in
[references/challenge_playbook.md](references/challenge_playbook.md).

- **Type d'entreprise** — propose 2-3 candidate company profiles from the
  activity, ask which resonates and why. Push for an observable signal that
  separates in-target from out-of-target, and whether it is a proven sale
  or a hypothesis.
- **Persona** — challenge "qui signe le chèque vs qui utilise vs qui
  prescrit ?". If the three are not the same person, help identify which one
  is the real commercial entry point.
- **Localisation** — challenge anything too broad. "France entière" for a
  first ICP is almost always too broad — push toward a testable geographic
  segment.

## Phase 3 — Handoff to context-write

Schema filled and challenged → call **context-write**, handing it:

1. the complete ICP object (per the schema);
2. the **mode** — `overwrite` with the target ICP id, or `append`;
3. the **id of the current workspace** (from `workspace.py status`).

Do not write the context yourself. Relay context-write's receipt to the
user, and state plainly that this is a **v1 falsifiable ICP** — the next
bricks (find → enrich → outreach) are what will validate or kill it.

## Transversal rules (always)

- Never ask a question whose answer is already in the input or the context.
- Always frame inferences as *"je suppose X — confirme ou corrige"* rather
  than *"quel est X ?"*.
- One question per turn, maximum.
- `confidence` always exits at `"hypothèse"` — it is the downstream bricks
  (outreach, ads) that surface real validation.
- Never claim the produced ICP is "the right ICP" — it is a falsifiable v1.

## Validation

Test prompts covering cases A–D and the drive-without-material scenario are
in [references/test_prompts.md](references/test_prompts.md).
