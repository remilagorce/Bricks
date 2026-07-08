#!/usr/bin/env python3
"""deploy_landing.py — Deploy a landing page HTML to Vercel, via GitHub.

Stdlib-only. Shells out to `git`, `gh` (GitHub CLI) and `vercel` (Vercel CLI).

Two modes:

  --check    Preflight: report which tools/credentials are present and, for
             every missing one, the exact command the user must run. Exit 0
             when everything is ready, 1 otherwise. NEVER prompts.

  --deploy   Scaffold a deploy directory (index.html + .gitignore), commit,
             create/push the GitHub repo, deploy to Vercel production, and
             print the resulting URLs. Idempotent: re-running redeploys.

Usage:
    python deploy_landing.py --check --output json
    python deploy_landing.py --deploy \
        --html ./landing-pages/quill-ai.html \
        --project landing-quill-ai \
        --output json
    python deploy_landing.py --deploy --html f.html --project p \
        --visibility public --vercel-token XXXX --vercel-scope my-team

Credentials resolution order:
  GitHub : `gh auth status` session, else GH_TOKEN / GITHUB_TOKEN env var.
  Vercel : --vercel-token flag, else VERCEL_TOKEN env var, else
           `vercel whoami` session.

NO LLM CALLS. Pure subprocess orchestration.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

CMD_TIMEOUT = 300  # seconds; vercel deploy of a static page is fast


# ---------------------------------------------------------------- helpers

def run(cmd: List[str], cwd: Optional[Path] = None,
        timeout: int = CMD_TIMEOUT) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, capture_output=True,
        text=True, timeout=timeout,
    )


def ok(cp: subprocess.CompletedProcess) -> bool:
    return cp.returncode == 0


def vercel_cmd(base: List[str], token: Optional[str],
               scope: Optional[str]) -> List[str]:
    cmd = list(base)
    if token:
        cmd += ["--token", token]
    if scope:
        cmd += ["--scope", scope]
    return cmd


# ---------------------------------------------------------------- preflight

def preflight(vercel_token: Optional[str],
              vercel_scope: Optional[str]) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ready: bool, detail: str, fix: str = "") -> None:
        checks.append({"name": name, "ready": ready,
                       "detail": detail, "fix": fix if not ready else ""})

    # git
    git = shutil.which("git")
    add("git", bool(git), git or "git not found on PATH",
        "Install Xcode command line tools: xcode-select --install")

    # gh CLI + auth
    gh = shutil.which("gh")
    add("gh_cli", bool(gh), gh or "GitHub CLI (gh) not found on PATH",
        "brew install gh")
    gh_env_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if gh:
        auth = run(["gh", "auth", "status"])
        gh_ready = ok(auth) or bool(gh_env_token)
        detail = ("authenticated via `gh auth login` session" if ok(auth)
                  else "GH_TOKEN/GITHUB_TOKEN env var set" if gh_env_token
                  else "gh installed but not authenticated")
        add("gh_auth", gh_ready, detail,
            "Run interactively: gh auth login  "
            "(or export GH_TOKEN=<personal access token with repo scope>)")
    else:
        add("gh_auth", False, "cannot check auth without gh",
            "Install gh first, then: gh auth login")

    # vercel CLI + auth
    vc = shutil.which("vercel")
    add("vercel_cli", bool(vc), vc or "Vercel CLI not found on PATH",
        "npm install -g vercel")
    token = vercel_token or os.environ.get("VERCEL_TOKEN")
    if vc:
        if token:
            who = run(vercel_cmd(["vercel", "whoami"], token, vercel_scope))
            add("vercel_auth", ok(who),
                f"token accepted (user: {who.stdout.strip()})" if ok(who)
                else "provided/env VERCEL_TOKEN was rejected",
                "Create a token at https://vercel.com/account/tokens and "
                "pass it via --vercel-token or VERCEL_TOKEN")
        else:
            who = run(["vercel", "whoami"])
            add("vercel_auth", ok(who),
                f"authenticated via `vercel login` session "
                f"(user: {who.stdout.strip()})" if ok(who)
                else "vercel installed but not authenticated",
                "Run interactively: vercel login  (or create a token at "
                "https://vercel.com/account/tokens and pass VERCEL_TOKEN)")
    else:
        add("vercel_auth", False, "cannot check auth without vercel CLI",
            "Install the CLI first, then: vercel login")

    return {"ready": all(c["ready"] for c in checks), "checks": checks}


# ---------------------------------------------------------------- deploy

def sanitize_project(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:80] or "landing-page"


def scaffold(html: Path, deploy_dir: Path) -> None:
    deploy_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(html, deploy_dir / "index.html")
    gitignore = deploy_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(".vercel\n.DS_Store\n")


def git_commit(deploy_dir: Path, steps: List[str]) -> None:
    if not (deploy_dir / ".git").is_dir():
        run(["git", "init", "-b", "main"], cwd=deploy_dir)
        steps.append("git init (branch main)")
    run(["git", "add", "-A"], cwd=deploy_dir)
    dirty = run(["git", "status", "--porcelain"], cwd=deploy_dir).stdout.strip()
    if dirty:
        cp = run(["git", "commit", "-m", "Deploy landing page"], cwd=deploy_dir)
        if not ok(cp):
            raise RuntimeError(f"git commit failed: {cp.stderr.strip()}")
        steps.append("git commit")
    else:
        steps.append("git commit skipped (no changes)")


def github_push(deploy_dir: Path, project: str, visibility: str,
                steps: List[str]) -> Optional[str]:
    branch = run(["git", "symbolic-ref", "--short", "HEAD"],
                 cwd=deploy_dir).stdout.strip() or "main"
    has_origin = ok(run(["git", "remote", "get-url", "origin"], cwd=deploy_dir))

    if not has_origin:
        cp = run(["gh", "repo", "create", project, f"--{visibility}",
                  "--source", ".", "--remote", "origin", "--push"],
                 cwd=deploy_dir)
        if ok(cp):
            steps.append(f"gh repo create {project} ({visibility}) + push")
        elif "already exists" in (cp.stderr + cp.stdout).lower():
            view = run(["gh", "repo", "view", project,
                        "--json", "url", "-q", ".url"], cwd=deploy_dir)
            if not ok(view):
                raise RuntimeError(
                    f"repo name '{project}' exists but is not yours/viewable: "
                    f"{view.stderr.strip()}")
            run(["git", "remote", "add", "origin", view.stdout.strip()],
                cwd=deploy_dir)
            push = run(["git", "push", "-u", "origin", branch], cwd=deploy_dir)
            if not ok(push):
                raise RuntimeError(f"git push failed: {push.stderr.strip()}")
            steps.append(f"reused existing repo {project} + push")
        else:
            raise RuntimeError(f"gh repo create failed: {cp.stderr.strip()}")
    else:
        push = run(["git", "push", "-u", "origin", branch], cwd=deploy_dir)
        if not ok(push):
            raise RuntimeError(f"git push failed: {push.stderr.strip()}")
        steps.append("git push to existing origin")

    view = run(["gh", "repo", "view", "--json", "url", "-q", ".url"],
               cwd=deploy_dir)
    return view.stdout.strip() if ok(view) else None


def vercel_deploy(deploy_dir: Path, project: str, token: Optional[str],
                  scope: Optional[str], steps: List[str]) -> str:
    link = run(vercel_cmd(["vercel", "link", "--yes", "--project", project],
                          token, scope), cwd=deploy_dir)
    steps.append("vercel link" if ok(link)
                 else "vercel link failed — deploy will use directory name")

    cp = run(vercel_cmd(["vercel", "deploy", "--prod", "--yes"], token, scope),
             cwd=deploy_dir)
    if not ok(cp):
        raise RuntimeError(f"vercel deploy failed: {cp.stderr.strip()[-800:]}")
    steps.append("vercel deploy --prod")

    urls = re.findall(r"https://[^\s]+\.vercel\.app", cp.stdout + cp.stderr)
    if not urls:
        raise RuntimeError("vercel deploy succeeded but no URL found in output")
    return urls[-1]


def resolve_production_url(project: str, deployment_url: str) -> str:
    """The generic domain is <project>.vercel.app; confirm it responds."""
    candidate = f"https://{project}.vercel.app"
    try:
        req = urllib.request.Request(candidate, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status < 500:
                return candidate
    except Exception:
        pass
    return deployment_url


def vercel_git_connect(deploy_dir: Path, token: Optional[str],
                       scope: Optional[str], steps: List[str]) -> None:
    """Best-effort: link the GitHub repo so future pushes auto-deploy."""
    cp = run(vercel_cmd(["vercel", "git", "connect", "--yes"], token, scope),
             cwd=deploy_dir)
    steps.append("vercel git connect (pushes auto-deploy)" if ok(cp)
                 else "vercel git connect skipped (GitHub app not installed "
                      "on this Vercel account — pushes will not auto-deploy)")


def deploy(html: Path, project: str, visibility: str,
           vercel_token: Optional[str], vercel_scope: Optional[str],
           deploy_root: Optional[Path]) -> Dict[str, Any]:
    if not html.is_file():
        raise RuntimeError(f"HTML file not found: {html}")
    project = sanitize_project(project)
    root = deploy_root or (html.parent / "deploys")
    deploy_dir = root / project
    steps: List[str] = []

    scaffold(html, deploy_dir)
    steps.append(f"scaffolded {deploy_dir}/index.html")
    git_commit(deploy_dir, steps)
    repo_url = github_push(deploy_dir, project, visibility, steps)
    token = vercel_token or os.environ.get("VERCEL_TOKEN")
    deployment_url = vercel_deploy(deploy_dir, project, token,
                                   vercel_scope, steps)
    production_url = resolve_production_url(project, deployment_url)
    vercel_git_connect(deploy_dir, token, vercel_scope, steps)

    return {
        "project": project,
        "deploy_dir": str(deploy_dir),
        "repo_url": repo_url,
        "repo_visibility": visibility,
        "deployment_url": deployment_url,
        "production_url": production_url,
        "steps": steps,
    }


# ---------------------------------------------------------------- CLI

def render_check(result: Dict[str, Any]) -> str:
    out = [f"Ready to deploy: {'YES' if result['ready'] else 'NO'}", ""]
    for c in result["checks"]:
        mark = "OK " if c["ready"] else "MISSING"
        out.append(f"[{mark}] {c['name']}: {c['detail']}")
        if c["fix"]:
            out.append(f"          fix: {c['fix']}")
    return "\n".join(out)


def render_deploy(result: Dict[str, Any]) -> str:
    out = [
        f"Project:        {result['project']}",
        f"Deploy dir:     {result['deploy_dir']}",
        f"GitHub repo:    {result['repo_url']} ({result['repo_visibility']})",
        f"Deployment:     {result['deployment_url']}",
        f"Production URL: {result['production_url']}",
        "",
        "Steps:",
    ]
    out += [f"  - {s}" for s in result["steps"]]
    return "\n".join(out)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true",
                      help="Preflight tools/credentials, never prompts")
    mode.add_argument("--deploy", action="store_true",
                      help="Scaffold, push to GitHub, deploy to Vercel")
    parser.add_argument("--html", help="Path to the landing page HTML")
    parser.add_argument("--project",
                        help="Project/repo name (kebab-case enforced)")
    parser.add_argument("--visibility", choices=["private", "public"],
                        default="private", help="GitHub repo visibility")
    parser.add_argument("--deploy-root",
                        help="Where deploy dirs live (default: <html dir>/deploys)")
    parser.add_argument("--vercel-token", help="Vercel token (else VERCEL_TOKEN "
                        "env var, else `vercel login` session)")
    parser.add_argument("--vercel-scope", help="Vercel team/scope slug")
    parser.add_argument("--output", choices=["human", "json"], default="human")
    args = parser.parse_args(argv)

    try:
        if args.check:
            result = preflight(args.vercel_token, args.vercel_scope)
            print(json.dumps(result, indent=2) if args.output == "json"
                  else render_check(result))
            return 0 if result["ready"] else 1

        if not args.html or not args.project:
            parser.error("--deploy requires --html and --project")
        result = deploy(
            html=Path(args.html).expanduser().resolve(),
            project=args.project,
            visibility=args.visibility,
            vercel_token=args.vercel_token,
            vercel_scope=args.vercel_scope,
            deploy_root=Path(args.deploy_root).expanduser().resolve()
            if args.deploy_root else None,
        )
        print(json.dumps(result, indent=2) if args.output == "json"
              else render_deploy(result))
        return 0
    except subprocess.TimeoutExpired as e:
        print(f"ERROR: command timed out: {' '.join(e.cmd)}", file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
