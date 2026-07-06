---
name: context-write
description: Écrit ou met à jour un ICP dans le contexte workspace selon le schéma ICP. Appelé par gtm-onboard, jamais directement.
user-invocable: false
---

# Context write

Takes one free-text sentence describing an ICP and writes it, structured,
into the current workspace's `context/icp.md`, following the ICP schema
verbatim. This is the one brick whose output is the context itself, not
database rows: no `db.py`, no `bricks.db` — just the markdown file the
other bricks read as their client brain. Called by `gtm-onboard`, never by
the user directly.

## Before anything: resolve the workspace

Follow `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` §2: run
`python3 "${CLAUDE_PLUGIN_ROOT}/tools/workspace.py" status`, `init` if
needed, and work exclusively inside the returned `current.path`. The target
file is `<current.path>/context/icp.md`. The FullEnrich gate (§4) and the
database rules (§5) do not apply here — this brick only edits markdown
under `context/`.

## Input

A single sentence (or short paragraph) carrying all the ICP facts, e.g.
« On vise les scale-ups SaaS B2B françaises de 50 à 500 salariés, on écarte
les <10 salariés et le secteur public, on cible les VP Sales et les Head of
Growth. » `gtm-onboard` hands it in — never re-interview the user here.

## Mapping — one fact, one field

Parse the sentence into this exact schema (identical to
`templates/context/icp.md`). Keep every heading and bullet label verbatim:

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
  `TODO` — never invent a size, a country, or a role that was not stated.
- **Kill rules** are hard disqualifiers only (« on écarte… », « pas de… »,
  « sauf… »): one bullet each, phrased as a condition a later brick can
  test (e.g. `fewer than 10 employees`, `secteur public`).
- **Buying roles**: title patterns in the target's own language,
  `|`-separated (e.g. `VP Sales|Head of Sales`); split decision-maker vs
  champion when the input distinguishes them, else fill only what is given.

## Write

1. Read the current `context/icp.md` first. This brick **updates**, it does
   not wipe: preserve the leading `<!-- … -->` guidance comment and any
   field already filled; only replace remaining `TODO`s and fields the new
   input actually addresses.
2. Write the file back with the edit tool — markdown only, schema headings
   unchanged.
3. Report a 3–4 line receipt: which fields were filled, which remain `TODO`.
   Never paste the whole file back into the chat.
