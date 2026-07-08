---
name: context-write
description: Écrit ou met à jour l'ICP et les personas dans le contexte workspace selon les schémas. Appelé par gtm-onboard, jamais directement.
user-invocable: false
---

# Context write

Takes one free-text sentence describing an ICP and writes it, structured,
into the current workspace's `context/icp.md`, following the ICP schema
verbatim. When `/bricks:gtm-onboard` also hands over a buying committee,
it persists one persona file per role under `context/personas/`. This is
the one brick whose output is the context itself, not database rows: no
`db.py`, no `bricks.db` — just the markdown files the other bricks read
as their client brain. Called by `/bricks:gtm-onboard`, never by the user
directly.

## Before anything: resolve the workspace

Follow `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` §2: run
`python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/workspace.py" status` and work
exclusively inside the returned current workspace. The target file is
`<workspace>/context/icp.md`. The database rules (§4-§6) do not apply
here — this brick only edits markdown under `context/`.

## Input

A single sentence (or short paragraph) carrying all the ICP facts, e.g.
« On vise les scale-ups SaaS B2B françaises de 50 à 500 salariés, on
écarte les <10 salariés et le secteur public, on cible les VP Sales et
les Head of Growth. » `/bricks:gtm-onboard` hands it in — never
re-interview the user here.

## Mapping — one fact, one field

Parse the sentence into this exact schema (identical to
`templates/context/icp.md`). Keep every heading and bullet label
verbatim:

```markdown
# Ideal customer profile

## Target companies

- Industry / vertical: <…>
- Size: <…>
- Geography: <…>
- Other signals of fit: <…>

## Kill rules (hard disqualifiers — stop spending on these immediately)

- <one testable disqualifier per bullet>

## Buying roles

- Decision maker: <title patterns> (title patterns)
- Champion: <title patterns> (title patterns)
```

Mapping rules:

- One fact maps to one field. A field the input does not address stays
  `TODO` — never invent a size, a country, or a role that was not
  stated.
- **Kill rules** are hard disqualifiers only (« on écarte… », « pas
  de… », « sauf… »): one bullet each, phrased as a condition a later
  brick can test (e.g. `fewer than 10 employees`, `secteur public`).
- **Buying roles**: title patterns in the target's own language,
  `|`-separated (e.g. `VP Sales|Head of Sales`); split decision-maker vs
  champion when the input distinguishes them, else fill only what is
  given.

## Write

1. Read the current `context/icp.md` first. This brick **updates**, it
   does not wipe: preserve the leading `<!-- … -->` guidance comment and
   any field already filled; only replace remaining `TODO`s and fields
   the new input actually addresses.
2. Write the file back with the edit tool — markdown only, schema
   headings unchanged.
3. Report a 3–4 line receipt: which fields were filled, which remain
   `TODO`. Never paste the whole file back into the chat.

## Personas — one file per buying role

When `/bricks:gtm-onboard` hands over a buying committee (more than the
single decision-maker — a champion, an end user, a DG/office-manager
layer), do NOT let it live only in the conversation: persist it, or the
writing bricks never see it. For each identified role write
`context/personas/<slug>.md` (slug from the role, e.g. `daf`,
`chef-comptable`), following the shape of
`templates/context/personas/decision-maker.md` verbatim (headings: *Who
they are* / *What they care about* / *Objections* / *Angle that works* /
*Style*). Fill each section from what onboarding surfaced; leave a
section `TODO` rather than inventing it.

Same update-not-wipe discipline as the ICP: read an existing persona
file before overwriting, preserve filled sections. The buying roles line
in `icp.md` and the persona files must agree — the ICP names the title
patterns, the persona files carry the depth. Add the personas written to
the receipt (one line: "personas persistés : DAF, chef comptable").
