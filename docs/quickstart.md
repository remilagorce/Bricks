# Quickstart

1. In Claude Code:
   ```
   /plugin marketplace add remilagorce/bricks
   /plugin install bricks@bricks
   ```
2. Authenticate the engine once — `claude setup-token`, then in
   `~/.bricks/env`:
   ```
   CLAUDE_CODE_OAUTH_TOKEN=<token>
   BRIGHTDATA_API_TOKEN=<token>
   ```
3. Open Claude Code in an empty directory and ask for leads in plain
   language. Bricks creates a workspace, writes companies to its database,
   and enriches them after a previewed GO.
