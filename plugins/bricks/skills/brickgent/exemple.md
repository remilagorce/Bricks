# brickgent — galerie de prompts

Des prompts prêts à adapter, par cas d'usage. Règle d'or : toujours le
gabarit `###Context### / ###Instruction###`, une mission précise (quoi
trouver, ce qui compte comme réponse valide, où chercher d'abord).
Multi-lignes en base : brackets `{{nom_colonne}}` (les VRAIS noms de
colonnes, vus via `db.py schema`). Une ou quelques lignes fournies
directement : les vraies valeurs à la place des brackets, un prompt par
ligne.

Pendant le dry-run, `runner.py` streame chaque ligne terminée sur
**stderr** (`preview_row`) — relayer au fur et à mesure, ne pas attendre
le JSON final sur stdout.

## Cas 1 — news récentes sur le site (multi-lignes, web)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/runner.py" --table companies \
  --ai '{"prompt":"###Context###\nYou are a web research agent whose job is to find the right information by browsing the company website.\n###Instruction###\nBrowse the website of {{name}} ({{domain}}) looking for recent news: a blog post, a press release, a product launch, an award, a hire. Only keep items published on the official site itself, the more recent the better. If nothing dated is found, status not_found.",
         "schema":{"type":"object","properties":{"news_titre":{"type":"string"},"news_date":{"type":"string"},"news_url":{"type":"string"}}},
         "web":true,"model":"sonnet"}' \
  --status-col news_status --limit 10        # dry-run → GO → --commit
```

## Cas 2 — email de contact (multi-lignes, web)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/runner.py" --table companies \
  --ai '{"prompt":"###Context###\nYou are a web research agent whose job is to find the right information by browsing the company website.\n###Instruction###\nFind a contact email address for {{name}} ({{domain}}). Check /contact, /about, /mentions-legales and the footer first. Only return an address written on the official site — never guess or construct one. Prefer a named person over contact@/info@ when both appear.",
         "schema":{"type":"object","properties":{"email_contact":{"type":"string"},"email_page":{"type":"string"}}},
         "web":true,"model":"sonnet"}' \
  --status-col email_status --limit 10
```

## Cas 3 — infos pour l'ice breaker (multi-lignes, web)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/runner.py" --table companies \
  --ai '{"prompt":"###Context###\nYou are a web research agent whose job is to find the right information by browsing the company website.\n###Instruction###\nBrowse the website of {{name}} ({{domain}}) and collect ONE specific, recent, verifiable fact usable to open a cold email: a client win, a new office, a product update, a stated value, an event. It must be specific to THIS company (no generic claims) and traceable to a page.",
         "schema":{"type":"object","properties":{"fait_icebreaker":{"type":"string"},"fait_url":{"type":"string"}}},
         "web":true,"model":"sonnet"}' \
  --status-col icebreaker_status --limit 10
```

## Cas 4 — jugement sans web (multi-lignes, pas de web)

L'agent juge UNIQUEMENT sur les colonnes déjà remplies (plus rapide,
moins cher — `haiku` suffit souvent) :

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/runner.py" --table companies \
  --ai '{"prompt":"###Context###\nYou are a classification agent. You judge ONLY from the data provided.\n###Instruction###\nD'\''après sa description : {{description}}, classe {{name}} en agence, editeur, ecommerce ou autre.",
         "schema":{"type":"object","properties":{"type_entreprise":{"type":"string"}}},
         "web":false,"model":"haiku"}' \
  --status-col type_status --limit 10
```

## Cas 5 — une ou quelques lignes fournies directement (sans moteur)

L'utilisateur donne les infos en langage naturel (« regarde ce que fait
dupont-menuiserie.fr, et aussi acme.com ») : prompts construits à la
volée avec les VRAIES valeurs (pas de brackets), puis **un sous-agent
détaché par ligne** (outil Agent, general-purpose), tirés EN PARALLÈLE —
côté session, zéro clé API. Le prompt du sous-agent :

```
###Context###
You are a web research agent whose job is to find the right information
by browsing the company website. Use the Bright Data MCP tools
(mcp__…brightdata__*) to browse. Return ONLY the answer.
###Instruction###
Browse dupont-menuiserie.fr and say in one sentence what the company
does and for whom. Include the URL of the page that proves it.
```

→ réponse relayée telle quelle ; stockage optionnel via `db.py modify`.

Variante commande (script, JSON garanti, ou MCP non connecté) :

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/agent.py" --model haiku --web \
  --prompt '###Context### … ###Instruction### Browse dupont-menuiserie.fr …'
# → {"ok": true, "output": "…"}
```

Variante JSON garanti (pour un script) : `--schema` avec un schéma JSON
inline :

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/agent.py" --model haiku --web \
  --prompt '…' \
  --schema '{"type": "object",
             "properties": {"activite": {"type": "string"},
                            "preuve": {"type": "string"}},
             "required": ["activite", "preuve"],
             "additionalProperties": false}'
# → {"ok": true, "output": {"activite": "…", "preuve": "https://…"}}
```

Au-delà d'une poignée de lignes (~5-10) : `db.py add` (ou `import-csv`)
puis le moteur avec brackets — dry-run, GO, commit.
