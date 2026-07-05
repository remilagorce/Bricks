# Test prompts — gtm-onboard

Five prompts to validate routing, inference-first discovery, and the
challenge round. Expected behaviour noted per case.

## 1. Empty input (case A)

```
(the user opens with nothing / an empty message)
```

Expect: workspace inspected, context empty → Phase 1. The agent drives with
a first concrete hypothesis instead of a blank interrogation, one question
at a time.

## 2. Rich input (case A, heavy inference)

```
Je vends un SaaS de conformité RGPD aux cliniques privées en France
```

Expect: massive inference from the sentence (secteur = santé/cliniques
privées, produit = SaaS conformité RGPD, localisation = France, persona
likely DPO / directeur d'établissement). Very few questions — mostly
confirmations phrased as « je suppose X — confirme ou corrige ». Challenge
pushes France → a tighter first segment.

## 3. Second ICP in the same workspace (case C, append)

```
Je veux définir mon deuxième ICP
```

(input coherent with the current workspace, at least one ICP already defined)

Expect: case C → the agent asks « tu veux modifier l'ICP existant [nom/id],
ou ajouter un nouvel ICP ? », lists existing ICPs with ids if several, sets
mode `append`, runs discovery for a fresh ICP, hands off to context-write in
`append`.

## 4. Manifestly different project (case D)

```
(current workspace = B2B SaaS in France; user:)
Je veux attaquer les restaurants indépendants à New York avec une app de réservation
```

Expect: divergence on ≥2 of {secteur, produit, marché} → case D. The agent
does NOT decide alone: it proposes creating a new workspace and asks. On yes
→ workspace handoff (banner shown), then Phase 1. On no → continue here in
mode `append`.

## 5. Deliberately vague (drive without material)

```
J'ai une idée de business
```

Expect: the agent still drives — proposes a concrete first hypothesis for
each schema field and lets the user react, one question at a time, rather
than dumping open questions. Confidence stays `"hypothèse"`.
