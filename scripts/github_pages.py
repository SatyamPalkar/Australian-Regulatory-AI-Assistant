"""Manage this repository's Pages deployment using existing Git authentication.

Credentials stay in process memory and are never written or printed.
"""
import argparse
import json
import os
import subprocess
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

OWNER = "SatyamPalkar"
REPO = "Australian-Regulatory-AI-Assistant"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"


def credential():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    result = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n", text=True,
        capture_output=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}, timeout=30,
    )
    values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    return values.get("password")


def request(path="", method="GET", body=None, token=None, allow_missing=False):
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "Australian-Regulatory-Assistant-Deployment"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    raw = json.dumps(body).encode() if body is not None else None
    if raw is not None:
        headers["Content-Type"] = "application/json"
    try:
        with urlopen(Request(API + path, headers=headers, data=raw, method=method), timeout=45) as response:
            data = response.read()
            return json.loads(data) if data else {}
    except HTTPError as exc:
        if exc.code == 404 and allow_missing:
            return None
        try:
            detail = json.loads(exc.read()).get("message", "GitHub request failed")
        except (ValueError, OSError):
            detail = "GitHub request failed"
        raise RuntimeError(f"GitHub returned HTTP {exc.code}: {detail}") from None


def main():
    parser = argparse.ArgumentParser(description="GitHub Pages deployment for this repository")
    parser.add_argument("command", choices=["status", "enable", "runs", "dispatch", "jobs"])
    parser.add_argument("--run-id", type=int)
    args = parser.parse_args()
    token = credential()
    try:
        if args.command == "status":
            repo = request(token=token)
            pages = request("/pages", token=token, allow_missing=True)
            print(json.dumps({"repository": repo["full_name"], "private": repo["private"], "permissions": repo.get("permissions"), "authenticated": bool(token), "pages": pages}, indent=2))
        elif args.command == "enable":
            if not token:
                raise RuntimeError("No existing GitHub credential is available to configure Pages")
            pages = request("/pages", token=token, allow_missing=True)
            if pages and pages.get("cname"):
                raise RuntimeError("Pages already has a custom domain; preserve it and review settings before changing hosting")
            if pages is None:
                pages = request("/pages", "POST", {"build_type": "workflow"}, token)
            elif pages.get("build_type") != "workflow":
                request("/pages", "PUT", {"build_type": "workflow"}, token)
                pages = request("/pages", token=token)
            print(json.dumps({"html_url": pages.get("html_url"), "build_type": pages.get("build_type"), "status": pages.get("status")}, indent=2))
        elif args.command == "runs":
            result = request("/actions/workflows/pages.yml/runs?branch=main&per_page=5", token=token, allow_missing=True)
            print(json.dumps([{key: run.get(key) for key in ("id", "head_sha", "status", "conclusion", "html_url", "created_at")} for run in (result or {}).get("workflow_runs", [])], indent=2))
        elif args.command == "dispatch":
            request("/actions/workflows/pages.yml/dispatches", "POST", {"ref": "main"}, token)
            print("Requested the GitHub Pages workflow on main.")
        else:
            if not args.run_id:
                parser.error("jobs requires --run-id")
            result = request(f"/actions/runs/{args.run_id}/jobs", token=token)
            print(json.dumps([{key: job.get(key) for key in ("id", "name", "status", "conclusion", "steps")} for job in result["jobs"]], indent=2))
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
