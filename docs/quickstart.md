# Quickstart

1. In Claude Code:
   ```
   /plugin marketplace add remilagorce/bricks
   /plugin install bricks@bricks
   ```
2. Inside a Claude Code session, engine workers inherit the parent's
   subscription (Keychain via the system `claude` CLI — no separate token
   file required). Optional `~/.bricks/env` only for standalone runs outside
   a session, or for `BRIGHTDATA_API_TOKEN` when Bright Data isn't connected
   via `/mcp`.
3. Open Claude Code in an empty directory and ask for leads in plain
   language. Bricks creates a workspace, writes companies to its database,
   and enriches them after a previewed GO.
