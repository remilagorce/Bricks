# brickgent — galerie de prompts

Des prompts prêts à adapter, par cas d'usage. Règle d'or : toujours le
gabarit `###Context### / ###Instruction###`, une mission précise (quoi
trouver, ce qui compte comme réponse valide, où chercher d'abord).
Multi-lignes en base : brackets `{{nom_colonne}}` (les VRAIS noms de
colonnes, vus via `db.py schema`). Une ou quelques lignes fournies
directement : les vraies valeurs à la place des brackets, un prompt par
ligne.

## Cas 1 — news récentes sur le site (multi-lignes, web)

```bash
python3 tools/runner.py run --db <bricks.db> --table companies \
  --claim news_status --handler agent --tools web --model sonnet \
  --prompt '###Context###
You are a web research agent whose job is to find the right information
by browsing the company website.
###Instruction###
Browse the website of {{name}} ({{domain}}) looking for recent news:
a blog post, a press release, a product launch, an award, a hire.
Only keep items published on the official site itself, the more recent
the better. If nothing dated is found, status not_found.' \
  --schema '{"fields": {"news_titre": "titre exact de la news la plus récente",
                        "news_date": "date de publication si affichée",
                        "news_url": "URL de la page de la news"},
             "evidence": true}' \
  --run-id news-<date> --limit 10        # dry-run → GO → --commit
```

## Cas 2 — email de contact (multi-lignes, web)

```bash
… --claim email_status --handler agent --tools web --model sonnet \
  --prompt '###Context###
You are a web research agent whose job is to find the right information
by browsing the company website.
###Instruction###
Find a contact email address for {{name}} ({{domain}}). Check /contact,
/about, /mentions-legales and the footer first. Only return an address
written on the official site — never guess or construct one. Prefer a
named person over contact@/info@ when both appear.' \
  --schema '{"fields": {"email_contact": "adresse email trouvée sur le site",
                        "email_page": "URL de la page où elle apparaît"},
             "evidence": true}' \
  --run-id email-<date> --limit 10
```

## Cas 3 — infos pour l'ice breaker (multi-lignes, web)

```bash
… --claim icebreaker_status --handler agent --tools web --model sonnet \
  --prompt '###Context###
You are a web research agent whose job is to find the right information
by browsing the company website.
###Instruction###
Browse the website of {{name}} ({{domain}}) and collect ONE specific,
recent, verifiable fact usable to open a cold email: a client win, a
new office, a product update, a stated value, an event. It must be
specific to THIS company (no generic claims) and traceable to a page.' \
  --schema '{"fields": {"fait_icebreaker": "le fait, une phrase factuelle",
                        "fait_url": "URL de la page qui le prouve"},
             "evidence": true}' \
  --run-id ice-<date> --limit 10
```

## Cas 4 — jugement sans web (multi-lignes, --tools none)

L'agent juge UNIQUEMENT sur les colonnes déjà remplies (plus rapide,
moins cher — `haiku` suffit souvent) :

```bash
… --claim type_status --handler agent --tools none --model haiku \
  --prompt '###Context###
You are a classification agent. You judge ONLY from the data provided.
###Instruction###
D'\''après sa description : {{description}}, classe {{name}} en
"agence", "editeur", "ecommerce" ou "autre".' \
  --schema '{"fields": {"type_entreprise": "agence|editeur|ecommerce|autre"},
             "evidence": false}' \
  --run-id type-<date> --limit 10
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
python3 tools/agents/researcher.py --model haiku --tools web \
  --prompt '###Context### … ###Instruction### Browse dupont-menuiserie.fr …'
# → {"ok": true, "output": "…", "costUsd": 0.004, "numTurns": 3}
```

Variante JSON garanti (pour un script) : `--structured` avec un schéma
JSON inline :

```bash
python3 tools/agents/researcher.py --model haiku --tools web \
  --prompt '…' \
  --structured '{"type": "object",
                 "properties": {"activite": {"type": "string"},
                                "preuve": {"type": "string"}},
                 "required": ["activite", "preuve"],
                 "additionalProperties": false}'
# → {"ok": true, "output": {"activite": "…", "preuve": "https://…"}, …}
```

Au-delà d'une poignée de lignes (~5-10) : `db.py add` (ou `import-csv`)
puis le moteur avec brackets — dry-run, GO, commit.
