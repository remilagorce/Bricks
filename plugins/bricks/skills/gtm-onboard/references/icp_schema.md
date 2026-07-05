# ICP schema — the data contract

Phase 1 fills this object. Respect it strictly: same keys, same nesting.
`gtm-onboard` produces it; `context-write` persists it. Do not add or rename
fields.

```json
{
  "id": "slug court unique",
  "company": {
    "secteur": "...",
    "taille": "TPE|PME|ETI|GE + effectif indicatif",
    "maturité": "seed|growth|scale|established",
    "signaux_qualification": ["signaux observables qui distinguent cible / hors cible"],
    "localisation": "zone géographique cible"
  },
  "persona": {
    "titre": "intitulé de poste principal",
    "role_decision": "décideur|prescripteur|utilisateur|acheteur",
    "pain_principal": "...",
    "trigger_achat": "événement observable qui déclenche le besoin"
  },
  "canal_prioritaire": "cold email|meta ads|linkedin|...|à tester",
  "confidence": "hypothèse|validé_qualitatif|validé_quantitatif",
  "validated_by": null
}
```

## Field notes

- **`id`** — a short unique slug (e.g. `cliniques-rgpd-fr`). If the workspace
  already holds ICPs, make sure it does not collide.
- **`company.signaux_qualification`** — observable signals only, phrased so a
  later brick could test them (e.g. « a un DPO nommé », « > 3 établissements »).
  These are what separate in-target from out-of-target.
- **`company.localisation`** — a testable segment, not a whole country by
  default (see the challenge playbook).
- **`persona.role_decision`** — the person's function in the buying decision;
  distinct from `titre` (their job title).
- **`persona.trigger_achat`** — an observable event, not a feeling
  (e.g. « levée de fonds », « nouveau règlement », « ouverture d'un site »).
- **`confidence`** — always `"hypothèse"` at the end of onboarding. It is not
  gtm-onboard's job to raise it.
- **`validated_by`** — always `null` on exit from onboarding.

## Exit condition

Every field is filled EXCEPT `validated_by` (stays `null`) and `confidence`
(stays `"hypothèse"`). That is the stop condition for Phase 1.
