# Deploy — GitHub → Vercel, fully programmatic

This file is the deployment engine for `create-landing-page`. It ships a
validated landing page HTML to a **generic Vercel domain**
(`https://<project>.vercel.app`) by first pushing it to a GitHub repo,
then deploying that repo's content to Vercel production. Everything runs
through one script:

```
${CLAUDE_PLUGIN_ROOT}/skills/create-landing-page/scripts/deploy_landing.py
```

Do not hand-run `git`/`gh`/`vercel` commands yourself — the script owns
that orchestration (scaffold, commit, repo create/reuse, deploy, alias
resolution). Your job is three phases: preflight, deploy, receipt.

## Phase A — Preflight (credentials & tools)

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/create-landing-page/scripts/deploy_landing.py" \
  --check --output json
```

Exit 0 → everything ready, go to Phase B without asking anything.

Exit 1 → some checks failed. The JSON tells you exactly what is missing
and the `fix` for each. Relay **only the failing items** to the user, as
copy-pasteable commands, then stop and wait:

- **Missing CLI** (`git`, `gh_cli`, `vercel_cli`) → give the install
  command from `fix` (e.g. `brew install gh`, `npm install -g vercel`).
- **`gh_auth` missing** → interactive login is the preferred path: tell
  the user to type `! gh auth login` in the prompt (the `!` prefix runs
  it interactively in this session). Alternative: a personal access
  token with `repo` scope in `GH_TOKEN`.
- **`vercel_auth` missing** → tell the user to type `! vercel login`,
  **or** to create a token at https://vercel.com/account/tokens and give
  it to you — pass it with `--vercel-token` in Phase B (env vars do not
  persist between Bash calls, so the flag is the reliable route). If the
  user is on a Vercel team, also ask for the team slug (`--vercel-scope`).

After the user acts, re-run `--check`. Loop until exit 0. Never fake a
deploy, never skip preflight.

## Phase B — Deploy

Run (one command does GitHub + Vercel):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/create-landing-page/scripts/deploy_landing.py" \
  --deploy \
  --html "<workspace>/landing-pages/<slug>.html" \
  --project "landing-<slug>" \
  --output json
```

- `--project` — repo AND Vercel project name. Default to `landing-<slug>`
  (the script enforces kebab-case). The generic domain follows from it:
  `https://landing-<slug>.vercel.app`.
- `--visibility` — GitHub repo is `private` by default; only pass
  `public` if the user asks.
- Append `--vercel-token <token>` (and `--vercel-scope <team>`) only if
  collected in Phase A.

What the script does, in order: copies the HTML to
`<workspace>/landing-pages/deploys/<project>/index.html`, commits, creates
the GitHub repo (or reuses it — reruns are idempotent redeploys), runs
`vercel deploy --prod`, verifies the generic `<project>.vercel.app` alias
responds, and best-effort connects the repo to Vercel so future pushes
auto-deploy.

On exit 2, read stderr: it names the failing step. Fix the actual cause
(most often auth expired → back to Phase A, or repo name owned by someone
else → retry with a different `--project`). Do not retry the same command
verbatim more than once.

## Phase C — Receipt

From the JSON, report to the user:

- **Production URL** (`production_url`) — the generic Vercel domain, lead
  with this.
- GitHub repo URL + visibility.
- One line on auto-deploy: connected or not (see `steps`).

Do not paste the raw JSON or command logs. Then update the workspace
close-of-run files as instructed in SKILL.md (`memory/NOTES.md`,
`memory/state.json` → `lastLandingDeploy`).
