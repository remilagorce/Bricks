<p align="center">
  <img src="docs/assets/logo.svg" alt="Bricks logo" width="72" style="background:#ff5722;border-radius:12px;padding:8px;" />
</p>

<h1 align="center">Bricks</h1>

<p align="center">
  <strong>The open-source GTM engine.</strong><br/>
  Replace Clay with open source and native integrations — built for the age of Claude Code.
</p>

<p align="center">
  <a href="https://remilagorce.github.io/Bricks/">Documentation</a> ·
  <a href="#quickstart">Quickstart</a> ·
  <a href="#contributing">Contributing</a>
</p>

---

## What is Bricks? 

Bricks is an open-source alternative to Clay. Instead of paying per credit inside a closed spreadsheet, you compose your GTM workflows from open bricks connected directly to the native tools you already use.

- **Find** — source companies and contacts from open and native data sources
- **Transform** — clean, dedupe, and shape your data with simple building blocks
- **Enrich** — plug enrichment providers directly, no middleman markup
- **Automated inbound** — qualify and route inbound leads automatically
- **Signal** — listen to buying signals and trigger workflows on them

## Quickstart

### 1. Add the marketplace

In a Claude Code session, add this repo as a plugin marketplace — a local
checkout, or the GitHub repo once published:

```text
/plugin marketplace add /path/to/clay-gtm-agent
# or, once published:
/plugin marketplace add remilagorce/Bricks
```

### 2. Install the plugin

```text
/plugin install bricks@bricks
```

This installs the `bricks` plugin (skills, the `db-writer` agent, the
`fullenrich` MCP server, the local web UI) from the `bricks` marketplace.
Restart Claude Code once installation finishes.

### 3. Create a workspace and start working

From any directory outside this repo (workspaces are data, never
committed):

```text
mkdir -p ~/bricks-workspaces/demo && cd ~/bricks-workspaces/demo
claude
```

Just ask in natural language — Claude picks the right brick:

```text
Crée un workspace pour une campagne SaaS France, trouve 30 entreprises
SaaS de 10-50 employés, puis enrichis leurs emails.
```

No setup command needed: the first GTM request auto-initializes the
workspace and scaffolds `context/offer.md` and `context/icp.md`.

### Switch between workspaces

A workspace is one isolated client/campaign context (its own database,
its own `context/`). Ask in natural language, or invoke the `workspace`
skill directly:

```text
switch workspace acme-outbound
/workspace list
/workspace status
```

`new` and `switch` show a banner confirming which workspace is now active
— always check it before running anything that writes data.

### Write to the database

You never write to `bricks.db` yourself, and neither does any skill
directly: every insert/update/read is delegated to the **`db-writer`**
agent, the single place that knows how to call `tools/db.py`. In practice
this is invisible — just ask for the outcome ("enrichis les 40 entreprises
sans email"), and the skill in charge asks `db-writer` to do the actual
read/write and reports back a receipt (counts, not raw rows). See
`CLAUDE.md` and `plugins/bricks/CONVENTIONS.md` for the full rationale and
contract.

### Open the local UI

A Clay-like table view of the current workspace's database:

```text
ouvre l'interface
```

This runs the `interface` skill, which launches `front/server.py` in the
background and gives you a `http://127.0.0.1:4321` link — the same
`tools/db.py` code path as the skills, so the UI never drifts from what
the bricks actually wrote.

### Workflows vs natural language

For exploration or one-off requests, just talk to Claude — it reads each
skill's description and picks the right brick per step. For a sequence you
want to repeat identically (e.g. find → enrich → transform, every week),
define a workflow that **dispatches explicitly** to named agents instead
of letting Claude re-decide the routing each time. See `CLAUDE.md` for the
dispatch-vs-automatic-delegation distinction.

Full guide in the [documentation](https://remilagorce.github.io/Bricks/quickstart/).

## Documentation

The docs are built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) and published on GitHub Pages.

Run them locally:

```bash
pip install -r requirements.txt
mkdocs serve
```

## Contributing

Contributions are welcome! See the [Contribute](https://remilagorce.github.io/Bricks/contribute/) guide in the docs.

## License

MIT