#!/usr/bin/env python3
"""
Fetch the live star/fork/issue counts for this repository and write them to
data/repo_stats.json, so the generated site can show real GitHub numbers
instead of a static badge.

Usage:
    GH_TOKEN=... REPO_FULL_NAME=havaianasdestruido/top100 python scripts/fetch_repo_stats.py

If the request fails (offline, rate limited, ...), the existing
data/repo_stats.json is left untouched and the script exits 0: the site
builds fine without it and simply omits the live counters.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "repo_stats.json"


def main():
    repo = os.environ.get("REPO_FULL_NAME") or "havaianasdestruido/top100"
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    url = f"https://api.github.com/repos/{repo}"

    req = request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "top100-site-builder")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError, ValueError,
            UnicodeDecodeError) as exc:  # ValueError covers JSONDecodeError
        print(f"Could not fetch repo stats ({exc}); keeping existing file.", file=sys.stderr)
        return 0

    stats = {
        "full_name": body.get("full_name", repo),
        "html_url": body.get("html_url", f"https://github.com/{repo}"),
        "description": body.get("description", ""),
        "stars": body.get("stargazers_count", 0),
        "forks": body.get("forks_count", 0),
        "watchers": body.get("subscribers_count", body.get("watchers_count", 0)),
        "open_issues": body.get("open_issues_count", 0),
        "default_branch": body.get("default_branch", "main"),
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(
        f"  -> data/repo_stats.json ({stats['stars']} stars, "
        f"{stats['forks']} forks)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
