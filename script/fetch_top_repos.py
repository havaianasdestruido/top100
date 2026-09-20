#!/usr/bin/env python3
"""
Fetch the top 100 GitHub repositories for one or more programming languages
using the GitHub Search API, and write:

  data/JSONL/<language>.jsonl   -> one JSON object per line: the FULL raw
                                    repository object exactly as returned by
                                    the GitHub Search API. No fields are
                                    dropped, renamed, or reshaped.

  data/TOP_<LANGUAGE>_100.md    -> a human-readable Markdown table summary
                                    (rank, name, stars, forks, issues,
                                    license, last push, description).

Why this is lightweight on API calls
-------------------------------------
GitHub's Search API returns up to 100 items per page. Requesting
per_page=100 on GET /search/repositories therefore gets the "top 100
repos by stars" for a language in exactly ONE request. So:

    total API calls (happy path) == number of languages requested

No per-repo follow-up calls are made (that would be +100 calls/language).
The raw search result item already includes almost everything GitHub
returns for a repo (owner, license, topics, stats, timestamps, etc.), which
satisfies "all information GitHub returns" without the extra cost. If you
ever need the handful of fields that only the single-repo endpoint returns
(e.g. subscribers_count, network_count, parent/source for forks), see the
ENRICH_WITH_REPO_DETAILS flag below -- it's off by default because it
multiplies API usage by ~100x.

Rate limits handled
--------------------
- Authenticated (GITHUB_TOKEN in Actions): 30 requests/min for Search API.
- The script backs off on 403/429 responses using Retry-After /
  X-RateLimit-Reset headers, and adds a small pause between languages.
"""

import json
import os
import sys
import time
import urllib.parse
from pathlib import Path
from urllib import request, error

API_URL = "https://api.github.com/search/repositories"
PER_PAGE = 100  # GitHub's max per page -> "top 100" in a single call

# Set to True to additionally call GET /repos/{owner}/{repo} for every
# result, which returns a few extra fields the search endpoint omits.
# WARNING: this turns 1 call/language into ~101 calls/language.
ENRICH_WITH_REPO_DETAILS = False

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
JSONL_DIR = DATA_DIR / "JSONL"


def get_token():
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")


def api_request(url, token):
    req = request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "top-repos-workflow")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    return req


def build_search_request(language, token):
    query = f"language:{language}"
    url = (
        f"{API_URL}?q={urllib.parse.quote(query)}"
        f"&sort=stars&order=desc&per_page={PER_PAGE}&page=1"
    )
    return api_request(url, token)


def fetch_with_retry(req, max_retries=5):
    for attempt in range(1, max_retries + 1):
        try:
            with request.urlopen(req) as resp:
                remaining = resp.headers.get("X-RateLimit-Remaining")
                reset = resp.headers.get("X-RateLimit-Reset")
                body = json.loads(resp.read().decode("utf-8"))
                return body, remaining, reset
        except error.HTTPError as e:
            if e.code in (403, 429):
                retry_after = e.headers.get("Retry-After")
                reset = e.headers.get("X-RateLimit-Reset")
                if retry_after:
                    wait = int(retry_after) + 1
                elif reset:
                    wait = max(int(reset) - int(time.time()), 1) + 1
                else:
                    wait = 30 * attempt
                print(
                    f"  Rate limited (attempt {attempt}/{max_retries}). "
                    f"Sleeping {wait}s...",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("Exceeded max retries due to rate limiting.")


def enrich_repo(repo, token):
    """Optional: fetch the single-repo endpoint for a few extra fields."""
    full_name = repo.get("full_name")
    if not full_name:
        return repo
    url = f"https://api.github.com/repos/{full_name}"
    req = api_request(url, token)
    try:
        details, _, _ = fetch_with_retry(req, max_retries=3)
        merged = dict(repo)
        merged.update(details)
        return merged
    except error.HTTPError:
        return repo


def write_jsonl(language, items):
    JSONL_DIR.mkdir(parents=True, exist_ok=True)
    path = JSONL_DIR / f"{language.lower()}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for repo in items:
            f.write(json.dumps(repo, ensure_ascii=False))
            f.write("\n")
    return path


def md_escape(text):
    if text is None:
        return ""
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def write_markdown(language, items, total_count):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"TOP_{language.upper()}_100.md"
    lines = []
    lines.append(f"# Top {len(items)} {language} repositories on GitHub\n")
    lines.append(
        f"Ranked by stars. GitHub reports **{total_count:,}** total "
        f"repositories matching `language:{language}`. "
        f"Generated automatically by the `top-repos` workflow.\n"
    )
    lines.append(
        "| # | Repository | ⭐ Stars | 🍴 Forks | 🐛 Open Issues | "
        "License | Last Push | Description |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for i, repo in enumerate(items, start=1):
        name = md_escape(repo.get("full_name"))
        html_url = repo.get("html_url", "")
        stars = repo.get("stargazers_count", 0)
        forks = repo.get("forks_count", 0)
        issues = repo.get("open_issues_count", 0)
        license_obj = repo.get("license") or {}
        license_name = md_escape(
            license_obj.get("spdx_id") or license_obj.get("name") or "—"
        )
        pushed_at = md_escape((repo.get("pushed_at") or "")[:10])
        desc = md_escape(repo.get("description") or "")
        if len(desc) > 120:
            desc = desc[:117] + "..."
        lines.append(
            f"| {i} | [{name}]({html_url}) | {stars:,} | {forks:,} | "
            f"{issues:,} | {license_name} | {pushed_at} | {desc} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def fetch_language(language, token):
    print(f"Fetching top {PER_PAGE} '{language}' repos...")
    req = build_search_request(language, token)
    body, remaining, reset = fetch_with_retry(req)
    items = body.get("items", [])
    total_count = body.get("total_count", 0)
    incomplete = body.get("incomplete_results", False)

    if ENRICH_WITH_REPO_DETAILS:
        enriched = []
        for repo in items:
            enriched.append(enrich_repo(repo, token))
            time.sleep(1)  # stay well under the core API's rate limit
        items = enriched

    jsonl_path = write_jsonl(language, items)
    md_path = write_markdown(language, items, total_count)

    print(
        f"  -> {len(items)} repos | total_count={total_count} "
        f"incomplete_results={incomplete} | rate_remaining={remaining}"
    )
    print(f"  -> {jsonl_path.relative_to(ROOT)}")
    print(f"  -> {md_path.relative_to(ROOT)}")
    return remaining, reset


def main():
    languages_env = os.environ.get("LANGUAGES", "")
    languages = [l.strip() for l in languages_env.split(",") if l.strip()]
    if not languages:
        print("No languages provided via LANGUAGES env var.", file=sys.stderr)
        sys.exit(1)

    token = get_token()
    if not token:
        print(
            "Warning: no GH_TOKEN/GITHUB_TOKEN found; using unauthenticated "
            "requests (10 req/min search limit).",
            file=sys.stderr,
        )

    for idx, lang in enumerate(languages):
        remaining, reset = fetch_language(lang, token)
        is_last = idx == len(languages) - 1
        if is_last:
            continue
        if remaining is not None and int(remaining) <= 1:
            wait = max(int(reset) - int(time.time()), 1) + 1 if reset else 60
            print(f"Low on search rate limit, sleeping {wait}s before next language...")
            time.sleep(wait)
        else:
            # Search API allows 30 req/min authenticated; small buffer.
            time.sleep(2)


if __name__ == "__main__":
    main()
