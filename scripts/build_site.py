#!/usr/bin/env python3
"""
Build the static Top100 website from the data in data/.

Reads   data/JSONL/<language>.jsonl   (raw GitHub Search API objects)
        data/TOP_<LANGUAGE>_100.md    (for the reported total_count)
        data/meta.json                (refresh timestamps, record counts)
        data/repo_stats.json          (live star/fork counts for this repo)

Writes  index.html, languages/index.html, languages/<slug>.html,
        methodology.html, dataset.html, compare.html, faq.html, 404.html,
        assets/style.css, sitemap.xml, robots.txt, llms.txt, llms-full.txt,
        feed.xml

The output is plain static HTML with no JavaScript and no build-time network
access, so it can be committed to the repository and served by GitHub Pages
exactly as-is.
"""

from __future__ import annotations

import html
import json
import re
import statistics
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import site_content as C  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MONTHS = [
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
]
NAV = [
    ("index.html", "Home"),
    ("languages/index.html", "Languages"),
    ("methodology.html", "Methodology"),
    ("dataset.html", "Dataset"),
    ("compare.html", "Compare"),
    ("faq.html", "FAQ"),
]

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
CODE_RE = re.compile(r"`([^`]+)`")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def esc(text) -> str:
    return html.escape(str(text), quote=True)


def fmt(n) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "—"


def md_inline(text: str) -> str:
    """Escape text, turning [label](url) into an anchor and `x` into <code>x</code>."""
    out = esc(text)
    out = LINK_RE.sub(r'<a href="\2">\1</a>', out)
    out = CODE_RE.sub(r"<code>\1</code>", out)
    return out


def md_plain(text: str) -> str:
    """Strip the inline markup, leaving plain text for JSON-LD."""
    return CODE_RE.sub(r"\1", LINK_RE.sub(r"\1", text))


def parse_iso(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def human_date(dt: datetime) -> str:
    return f"{dt.day} {MONTHS[dt.month - 1]} {dt.year}"


def human_datetime(dt: datetime) -> str:
    return f"{dt.day} {MONTHS[dt.month - 1]} {dt.year}, {dt.hour:02d}:{dt.minute:02d} UTC"


def iso_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def jsonl_url(key: str) -> str:
    """Raw download URL for a language's JSONL file. '#' and '+' are
    percent-encoded so that c#.jsonl and c++.jsonl survive URL parsing
    instead of being read as a fragment."""
    return f"{C.RAW_URL}/data/JSONL/{quote(key, safe='')}.jsonl"


def md_file_url(key: str) -> str:
    """GitHub blob URL for a language's Markdown table (same encoding)."""
    return f"{C.BLOB_URL}/data/TOP_{quote(key.upper(), safe='')}_100.md"


def truncate(text, limit=140) -> str:
    text = (text or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def words(text: str) -> int:
    return len(re.sub(r"<[^>]+>", " ", md_plain(text)).split())


def write(rel_path: str, content: str) -> Path:
    path = ROOT / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return path  # unchanged: keeps the hourly diff small
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_jsonl(name: str):
    path = DATA / "JSONL" / f"{name}.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def parse_total_count(lang_key: str):
    path = DATA / f"TOP_{lang_key.upper()}_100.md"
    if not path.exists():
        return None
    m = re.search(r"reports \*\*([\d,]+)\*\*", path.read_text(encoding="utf-8"))
    return int(m.group(1).replace(",", "")) if m else None


def load_data():
    """Return {lang_key: {...}} for every language that has data on disk."""
    out = {}
    for key, display, slug, note in C.LANGUAGES:
        repos = load_jsonl(key)
        if not repos:
            continue
        repos.sort(key=lambda r: r.get("stargazers_count", 0), reverse=True)
        stars = [r.get("stargazers_count", 0) for r in repos]
        licenses = {}
        for r in repos:
            lic = (r.get("license") or {}).get("spdx_id") or "NOASSERTION"
            licenses[lic] = licenses.get(lic, 0) + 1
        top_license, top_license_n = max(licenses.items(), key=lambda kv: (kv[1], kv[0]))
        out[key] = {
            "key": key,
            "display": display,
            "slug": slug,
            "note": note,
            "repos": repos,
            "total_count": parse_total_count(key),
            "n": len(repos),
            "min_stars": min(stars),
            "median_stars": int(statistics.median(stars)),
            "max_stars": max(stars),
            "top_license": top_license,
            "top_license_n": top_license_n,
            "size_bytes": (DATA / "JSONL" / f"{key}.jsonl").stat().st_size,
        }
    return out


def load_meta():
    path = DATA / "meta.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def load_repo_stats():
    path = DATA / "repo_stats.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def build_context(langs):
    meta = load_meta()
    stats = load_repo_stats()
    all_repos = [r for info in langs.values() for r in info["repos"]]
    all_stars = [r.get("stargazers_count", 0) for r in all_repos]

    top_overall, seen = [], set()
    for r in sorted(all_repos, key=lambda r: r.get("stargazers_count", 0), reverse=True):
        name = r.get("full_name")
        if name in seen:
            continue
        seen.add(name)
        top_overall.append(r)
        if len(top_overall) >= 10:
            break

    fetched = parse_iso(meta.get("fetched_at", ""))
    if fetched is None:
        newest = max(
            (parse_iso(r.get("updated_at", "")) for r in all_repos if r.get("updated_at")),
            default=None,
        )
        fetched = newest or datetime.now(timezone.utc)

    bars = [info["min_stars"] for info in langs.values()] or [0]
    ctx = {
        "langs": langs,
        "meta": meta,
        "repo_stats": stats,
        "records": len(all_repos),
        "languages": len(langs),
        "top_overall": top_overall,
        "median_stars": int(statistics.median(all_stars)) if all_stars else 0,
        "mean_stars": int(statistics.mean(all_stars)) if all_stars else 0,
        "min_bar": min(bars),
        "max_bar": max(bars),
        "min_bar_lang": min(langs.values(), key=lambda i: i["min_stars"])["display"],
        "max_bar_lang": max(langs.values(), key=lambda i: i["min_stars"])["display"],
        "forks_in_data": sum(1 for r in all_repos if r.get("fork")),
        "archived_in_data": sum(1 for r in all_repos if r.get("archived")),
        "jsonl_bytes": sum(i["size_bytes"] for i in langs.values()),
        "total_matching": sum(i["total_count"] or 0 for i in langs.values()),
        "fetched": fetched,
        "date_long": human_date(fetched),
        "date_short": human_date(fetched),
        "datetime_long": human_datetime(fetched),
        "iso_date": iso_date(fetched),
        "rfc822": format_datetime(fetched),
    }
    ctx["fmt"] = fmt
    return ctx


# ---------------------------------------------------------------------------
# HTML shell
# ---------------------------------------------------------------------------

def jsonld_block(payload) -> str:
    return (
        '<script type="application/ld+json">'
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + "</script>"
    )


def html_page(*, ctx, prefix, title, description, canonical, body, jsonld,
              updated_line=None, active=None) -> str:
    nav = []
    for href, label in NAV:
        current = ' aria-current="page"' if href == active else ""
        nav.append(f'<a href="{prefix}{href}"{current}>{label}</a>')
    head_jsonld = "\n".join(jsonld_block(b) for b in jsonld)
    updated = f'<p class="updated">{updated_line}</p>' if updated_line else ""
    stats = ctx["repo_stats"]
    star_link = ""
    if stats:
        star_link = (
            f'<a class="brand-stars" href="{C.REPO_URL}">&#9733; '
            f"{fmt(stats.get('stars', 0))} on GitHub</a>"
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="generator" content="scripts/build_site.py">
<meta property="og:site_name" content="Top100">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta name="twitter:card" content="summary">
<link rel="alternate" type="application/rss+xml" title="Top100 data updates" href="{prefix}feed.xml">
<link rel="stylesheet" href="{prefix}assets/style.css">
{head_jsonld}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site">
<div class="wrap">
<a class="brand" href="{prefix}index.html">Top<span>100</span></a>
{star_link}
<nav class="site">
{"".join(nav)}
</nav>
</div>
</header>
<main id="main" class="wrap">
{updated}
{body}
</main>
<footer class="site">
<div class="wrap">
<span>Top100 &mdash; the 100 most-starred GitHub repositories for {ctx['languages']} languages.</span>
<a href="{C.REPO_URL}">GitHub repository</a>
<a href="{C.TREE_URL}/data/JSONL">JSONL data</a>
<a href="{prefix}feed.xml">Update feed</a>
<a href="{prefix}sitemap.xml">Sitemap</a>
<a href="{prefix}llms.txt">llms.txt</a>
<span>Data refreshed {ctx['datetime_long']} &middot; static site, no JavaScript</span>
</div>
</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Reusable fragments
# ---------------------------------------------------------------------------

def repo_table(repos, *, caption, limit=None, show_language=False):
    rows = repos if limit is None else repos[:limit]
    head = (
        "<tr><th class='num'>#</th><th>Repository</th>"
        + ("<th>Language</th>" if show_language else "")
        + "<th class='num'>&#9733; Stars</th><th class='num'>Forks</th>"
        "<th class='num'>Open issues</th><th>Licence</th><th>Last push</th>"
        "<th>Description</th></tr>"
    )
    body = []
    for i, r in enumerate(rows, start=1):
        lic = (r.get("license") or {}).get("spdx_id") or "—"
        pushed = (r.get("pushed_at") or "")[:10]
        desc = truncate(r.get("description"))
        lang_cell = f"<td>{esc(r.get('language') or '—')}</td>" if show_language else ""
        body.append(
            f"<tr><td class='rank'>{i}</td>"
            f"<td><a href='{esc(r.get('html_url', ''))}'>{esc(r.get('full_name', ''))}</a></td>"
            f"{lang_cell}"
            f"<td class='num stars'>{fmt(r.get('stargazers_count', 0))}</td>"
            f"<td class='num'>{fmt(r.get('forks_count', 0))}</td>"
            f"<td class='num'>{fmt(r.get('open_issues_count', 0))}</td>"
            f"<td>{esc(lic)}</td>"
            f"<td><time datetime='{esc(pushed)}'>{esc(pushed)}</time></td>"
            f"<td>{esc(desc)}</td></tr>"
        )
    return (
        f"<div class='tablewrap'><table>\n<caption>{caption}</caption>\n"
        f"<thead>{head}</thead>\n<tbody>\n" + "\n".join(body) + "\n</tbody>\n</table></div>"
    )


def stats_table(ctx):
    rows = []
    for key, info in sorted(ctx["langs"].items(), key=lambda kv: -kv[1]["max_stars"]):
        rows.append(
            f"<tr><td><a href='languages/{info['slug']}.html'>{esc(info['display'])}</a></td>"
            f"<td><a href='{esc(info['repos'][0].get('html_url', ''))}'>"
            f"{esc(info['repos'][0]['full_name'])}</a></td>"
            f"<td class='num stars'>{fmt(info['max_stars'])}</td>"
            f"<td class='num'>{fmt(info['min_stars'])}</td>"
            f"<td class='num'>{fmt(info['median_stars'])}</td>"
            f"<td class='num'>{fmt(info['total_count'])}</td>"
            f"<td>{esc(info['top_license'])} ({info['top_license_n']}/100)</td></tr>"
        )
    return (
        "<div class='tablewrap'><table>\n"
        "<caption>How hard is it to reach each language's top 100? "
        "“Stars to enter” is the star count of the 100th-ranked repository.</caption>\n"
        "<thead><tr><th>Language</th><th>Most-starred repository</th>"
        "<th class='num'>&#9733; Leader</th><th class='num'>Stars to enter top 100</th>"
        "<th class='num'>Median in top 100</th><th class='num'>Repos GitHub reports</th>"
        "<th>Most common licence</th></tr></thead>\n<tbody>\n"
        + "\n".join(rows)
        + "\n</tbody>\n</table></div>"
    )


def language_grid(ctx, *, exclude=None, columns_note=False):
    items = []
    for key, info in ctx["langs"].items():
        if exclude and key == exclude:
            continue
        sub = (
            f"{esc(info['repos'][0]['full_name'])} &middot; "
            f"<span class='stars'>{fmt(info['max_stars'])}</span> stars"
        )
        items.append(
            f"<li><a href='languages/{info['slug']}.html'>Top 100 {esc(info['display'])} "
            f"repositories</a><span class='sub'>{sub}</span></li>"
        )
    return "<ul class='grid'>\n" + "\n".join(items) + "\n</ul>"


def faq_html(entries, level: int = 3) -> str:
    tag = f"h{level}"
    out = []
    for q, a in entries:
        out.append(f"<{tag}>{esc(q)}</{tag}>\n<p>{md_inline(a)}</p>")
    return "\n".join(out)


def code_block(text) -> str:
    return f"<pre><code>{text}</code></pre>"


# ---------------------------------------------------------------------------
# JSON-LD
# ---------------------------------------------------------------------------

def org(ctx):
    return {
        "@type": "Organization",
        "name": C.REPO_FULL_NAME.split("/")[0],
        "url": f"https://github.com/{C.REPO_FULL_NAME.split('/')[0]}",
    }


def jsonld_website(ctx):
    return {
        "@type": "WebSite",
        "@id": f"{C.BASE_URL}/#website",
        "name": "Top100",
        "alternateName": "Top 100 GitHub repositories by language",
        "url": f"{C.BASE_URL}/",
        "inLanguage": "en",
        "description": (
            "The 100 most-starred GitHub repositories for 30 programming languages, "
            "refreshed hourly from the GitHub Search API and published as raw JSONL."
        ),
        "publisher": {"@id": f"{C.BASE_URL}/#org"},
        "dateModified": ctx["fetched"].strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def jsonld_software(ctx):
    return {
        "@type": "SoftwareApplication",
        "@id": f"{C.BASE_URL}/#software",
        "name": "Top100",
        "alternateName": "Top100 GitHub repositories by language",
        "url": f"{C.BASE_URL}/",
        "sameAs": C.REPO_URL,
        "applicationCategory": "DeveloperApplication",
        "operatingSystem": "Any (Python 3 and GitHub Actions)",
        "description": (
            "Open-source tool that fetches the 100 most-starred GitHub repositories "
            "for 30 programming languages with one Search API request per language, "
            "publishes them as HTML tables and raw JSONL, and refreshes them hourly "
            "via a scheduled GitHub Actions workflow."
        ),
        "featureList": [
            "Top 100 repositories by stars for 30 programming languages",
            "Raw, unmodified GitHub Search API repository objects as JSONL",
            "Hourly refresh via scheduled GitHub Actions workflow",
            "One Search API request per language",
            "Static website with per-language pages, methodology and field reference",
        ],
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "isAccessibleForFree": True,
        "creator": org(ctx),
        "dateModified": ctx["fetched"].strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def jsonld_dataset(ctx, key=None):
    if key is None:
        name = "Top 100 GitHub repositories by stars for 30 programming languages"
        desc = (
            f"{ctx['records']} GitHub repository records — the 100 most-starred "
            "repositories for each of 30 programming languages — as newline-delimited "
            "JSON. Each record is the complete, unmodified repository object returned "
            "by the GitHub Search API, refreshed hourly."
        )
        url = f"{C.BASE_URL}/"
        page = f"{C.BASE_URL}/dataset.html"
        keywords = ["github", "repositories", "stars", "ranking", "jsonl",
                    "open source", "dataset", "github api"]
        dist_url = f"{C.TREE_URL}/data/JSONL"
        distribution = [
            {
                "@type": "DataDownload",
                "name": f"Top 100 {i['display']} repositories (JSONL)",
                "encodingFormat": "application/x-ndjson",
                "contentUrl": jsonl_url(k),
            }
            for k, i in ctx["langs"].items()
        ]
    else:
        info = ctx["langs"][key]
        name = f"Top 100 {info['display']} repositories on GitHub by stars"
        desc = (
            f"The 100 most-starred {info['display']} repositories on GitHub, as "
            "newline-delimited JSON. Each record is the complete, unmodified "
            "repository object returned by the GitHub Search API, refreshed hourly."
        )
        url = f"{C.BASE_URL}/languages/{info['slug']}.html"
        page = url
        keywords = ["github", info["display"].lower(), "repositories", "stars",
                    "ranking", "jsonl", "dataset"]
        dist_url = jsonl_url(key)
        distribution = [
            {
                "@type": "DataDownload",
                "name": f"Top 100 {info['display']} repositories (JSONL)",
                "encodingFormat": "application/x-ndjson",
                "contentUrl": dist_url,
            }
        ]
    return {
        "@type": "Dataset",
        "@id": f"{page}#dataset",
        "name": name,
        "description": desc,
        "url": page,
        "sameAs": dist_url,
        "keywords": keywords,
        "license": "https://github.com/havaianasdestruido/top100/blob/main/LICENSE",
        "isAccessibleForFree": True,
        "creator": org(ctx),
        "publisher": org(ctx),
        "includedInDataCatalog": {"@type": "DataCatalog", "name": "Top100"},
        "temporalCoverage": f"{ctx['iso_date']}/..",
        "dateModified": ctx["fetched"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "distribution": distribution,
    }


def jsonld_faq(entries, page_url):
    return {
        "@type": "FAQPage",
        "@id": f"{page_url}#faq",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": md_plain(a)},
            }
            for q, a in entries
        ],
    }


def jsonld_breadcrumb(items, page_url):
    return {
        "@type": "BreadcrumbList",
        "@id": f"{page_url}#breadcrumb",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": url}
            for i, (name, url) in enumerate(items, start=1)
        ],
    }


def jsonld_webpage(ctx, *, name, description, page_url, page_type="WebPage"):
    return {
        "@type": page_type,
        "@id": f"{page_url}#webpage",
        "url": page_url,
        "name": name,
        "description": description,
        "inLanguage": "en",
        "isPartOf": {"@id": f"{C.BASE_URL}/#website"},
        "dateModified": ctx["fetched"].strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def jsonld_itemlist(items, page_url, name):
    return {
        "@type": "ItemList",
        "@id": f"{page_url}#itemlist",
        "name": name,
        "numberOfItems": len(items),
        "itemListOrder": "https://schema.org/ItemListOrderDescending",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i,
                "url": r.get("html_url", ""),
                "name": r.get("full_name", ""),
            }
            for i, r in enumerate(items, start=1)
        ],
    }


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def page_index(ctx):
    faq = C.faq_entries(ctx)
    top = ctx["top_overall"]
    top_names = ", ".join(r["full_name"] for r in top[:3])
    dataset_snippet = code_block(
        "# download one language\n"
        "curl -sSL -o python.jsonl \\\n"
        f"  {C.RAW_URL}/data/JSONL/python.jsonl\n"
        "\n"
        "# query it in place with DuckDB\n"
        'duckdb -c "SELECT full_name, stargazers_count, license.spdx_id\n'
        "          FROM read_json_auto('python.jsonl')\n"
        '          ORDER BY stargazers_count DESC LIMIT 10;"'
    )

    body = f"""
<h1>Top 100 GitHub repositories by stars, for every major language</h1>
<p class="lead">Top100 tracks the 100 most-starred GitHub repositories for
{ctx['languages']} programming languages and republishes the result every hour as a
plain, queryable dataset. Every row comes straight from the GitHub Search API &mdash;
the complete repository object, untouched &mdash; so you can rank, filter and analyse
it without scraping anything yourself. No API key, no rate limit, no sign-up: the
JSONL files are plain text you can download or <code>curl</code>.</p>

<ul class="facts">
<li><b>{ctx['languages']}</b> languages covered</li>
<li><b>{fmt(ctx['records'])}</b> repositories ranked</li>
<li><b>Hourly</b> refresh from the GitHub API</li>
<li><b>{round(ctx['jsonl_bytes'] / 1_048_576, 1)} MB</b> of raw JSONL</li>
<li><b>{fmt(ctx['total_matching'])}</b> repositories matched in total</li>
</ul>

<h2 id="right-now">What are the top GitHub repositories by stars right now?</h2>
<p>As of {ctx['date_long']}, the most-starred repositories on GitHub are led by
{top_names}. The table below is the overall top 10 across every language Top100
tracks; it is rebuilt every hour, and each language has its own top 100 list
underneath it.</p>
{repo_table(top, caption="The 10 most-starred GitHub repositories across all tracked languages, refreshed " + ctx['datetime_long'] + ".", show_language=True)}
<p class="small muted">Ranked by <code>stargazers_count</code> only. Star counts
accumulate for the lifetime of a repository, so this list rewards age as much as
quality &mdash; for what is trending <em>now</em>, GitHub Trending is the better
tool.</p>

<h2 id="languages">Top 100 repositories by language</h2>
<p>Each language has its own indexable page &mdash; Top 100 Python repositories, Top
100 Rust repositories, Top 100 Go repositories and so on &mdash; with the full
100-row table, the star count needed to reach 100th place, and a JSONL download.
Pick a language:</p>
{language_grid(ctx)}

<h2 id="statistics">How many stars does it take to reach a top 100?</h2>
<p>The answer varies by three orders of magnitude. Across the
{fmt(ctx['records'])} repositories in these lists the median is
{fmt(ctx['median_stars'])} stars and the mean is {fmt(ctx['mean_stars'])} &mdash;
the gap between the two is the skew of the distribution. Reaching 100th place takes
{fmt(ctx['min_bar'])} stars in {ctx['min_bar_lang']} and {fmt(ctx['max_bar'])} stars
in {ctx['max_bar_lang']}. Every figure below is recomputed on each refresh.</p>
{stats_table(ctx)}

<h2 id="dataset">Free JSONL dataset of GitHub repository metadata</h2>
<p>The dataset is {ctx['languages']} JSONL files, one per language, with 100 records
each &mdash; {fmt(ctx['records'])} repository objects in total. Every line is the
complete JSON object GitHub's Search API returned: owner, licence, topics, all
counts, all timestamps, all feature flags. Nothing is dropped, renamed or reshaped,
so the files load directly into DuckDB, pandas, jq or BigQuery.</p>
{dataset_snippet}
<p>See the <a href="dataset.html">dataset field reference</a> for a description of
every field, the <a href="methodology.html">methodology page</a> for the exact query
and refresh cadence, and the <a href="compare.html">comparison page</a> for how this
stacks up against GitHub Trending, gitstar-ranking.com and EvanLi/Github-Ranking.</p>

<h2 id="how">How the data is collected</h2>
<p>One GitHub Search API request per language:
<code>GET /search/repositories?q=language:Python&amp;sort=stars&amp;order=desc&amp;per_page=100</code>.
A scheduled GitHub Actions workflow runs that for all {ctx['languages']} languages
every hour, rebuilds the Markdown tables and this website, and commits the result
back to the repository. The whole pipeline is
{fmt(30)} requests per refresh &mdash; one per language &mdash; and the
<a href="methodology.html">methodology page</a> documents the query, the back-off
behaviour and the known limitations.</p>

<h2 id="compare">How Top100 compares to other GitHub ranking sites</h2>
<p>GitHub Trending shows what is hot today and offers no export.
gitstar-ranking.com and Top1000Repos publish global HTML leaderboards.
EvanLi/Github-Ranking publishes per-language Markdown tables daily. GH Archive and
BigQuery cover event history at petabyte scale. Top100's niche is the combination
those sources each miss: per-language depth <em>and</em> a raw JSONL export
<em>and</em> hourly freshness. The <a href="compare.html">full comparison</a> says
where it wins and where it does not.</p>

<h2 id="faq">Frequently asked questions</h2>
{faq_html(faq)}
<p class="small muted">More questions &mdash; licensing, refresh cadence, adding
languages, forks &mdash; are answered on the <a href="faq.html">FAQ page</a>.</p>
"""
    jsonld = [
        {"@context": "https://schema.org", "@graph": [
            jsonld_website(ctx),
            jsonld_software(ctx),
            jsonld_dataset(ctx),
            jsonld_faq(faq, f"{C.BASE_URL}/"),
            jsonld_webpage(ctx, name="Top 100 GitHub repositories by stars, for every major language",
                           description="Top 100 GitHub repositories by stars for 30 programming languages, with a free JSONL dataset refreshed hourly.",
                           page_url=f"{C.BASE_URL}/"),
        ]},
    ]
    return html_page(
        ctx=ctx, prefix="", title="Top 100 GitHub Repositories by Stars — 30 Languages, Free JSONL Dataset",
        description=(
            "Ranked lists of the 100 most-starred GitHub repositories for 30 programming "
            "languages, refreshed hourly from the GitHub Search API. Download the raw "
            "JSONL dataset of GitHub repository metadata for free."
        ),
        canonical=f"{C.BASE_URL}/",
        body=body, jsonld=jsonld,
        updated_line=f"Data refreshed {ctx['datetime_long']} &middot; next refresh within the hour",
        active="index.html",
    )


def page_languages_index(ctx):
    rows = []
    for key, info in ctx["langs"].items():
        rows.append(
            f"<tr><td><a href='{info['slug']}.html'>Top 100 {esc(info['display'])} repositories</a></td>"
            f"<td><a href='{esc(info['repos'][0].get('html_url', ''))}'>{esc(info['repos'][0]['full_name'])}</a></td>"
            f"<td class='num stars'>{fmt(info['max_stars'])}</td>"
            f"<td class='num'>{fmt(info['min_stars'])}</td>"
            f"<td class='num'>{fmt(info['median_stars'])}</td>"
            f"<td class='num'>{fmt(info['total_count'])}</td>"
            f"<td><a href='{jsonl_url(key)}'>JSONL</a></td></tr>"
        )
    body = f"""
<h1>Top 100 GitHub repositories for all {ctx['languages']} languages</h1>
<p class="lead">Every language Top100 tracks has its own page: a full 100-row table
ranked by stars, the star count needed to reach 100th place, the median star count
inside the top 100, and the raw JSONL for download.</p>
<div class='tablewrap'><table>
<caption>All {ctx['languages']} languages, ordered as on the homepage. Star counts refreshed {ctx['datetime_long']}.</caption>
<thead><tr><th>Language page</th><th>Most-starred repository</th>
<th class='num'>&#9733; Leader</th><th class='num'>Stars to enter top 100</th>
<th class='num'>Median in top 100</th><th class='num'>Repos GitHub reports</th>
<th>Data</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table></div>
<h2>What "primary language" means here</h2>
<p>GitHub assigns every repository a single detected primary language, so each
repository appears in exactly one list. A project that is half Python and half C++
is filed under whichever language GitHub detected as dominant, which is why the
per-language totals on this page do not add up to the number of repositories on
GitHub.</p>
<h2>Adding a language</h2>
<p>Fetching is free-form: trigger the workflow from the Actions tab with a
comma-separated list of languages, or run
<code>LANGUAGES=Rust,Zig python scripts/fetch_top_repos.py</code> locally. Each
language costs one Search API request.</p>
<p>Publishing it is a configuration step, not an automatic one. The site builder reads
the language list in <code>scripts/site_content.py</code>, so add a line there &mdash;
key, display name, URL slug and a one-line note &mdash; and the next build generates the
page. Until then the JSONL and Markdown files exist in the repository but no page is
published for them. Changing the builder to discover <code>data/</code> automatically
would remove that step. The <a href="../methodology.html">methodology page</a> has the
details.</p>
"""
    jsonld = [
        {"@context": "https://schema.org", "@graph": [
            jsonld_webpage(ctx, name=f"Top 100 GitHub repositories for all {ctx['languages']} languages",
                           description="Index of the top 100 most-starred GitHub repositories for 30 programming languages.",
                           page_url=f"{C.BASE_URL}/languages/index.html"),
            jsonld_breadcrumb([
                ("Top100", f"{C.BASE_URL}/"),
                ("Languages", f"{C.BASE_URL}/languages/index.html"),
            ], f"{C.BASE_URL}/languages/index.html"),
            jsonld_dataset(ctx),
        ]},
    ]
    return html_page(
        ctx=ctx, prefix="../", title=f"Top 100 GitHub Repositories for All {ctx['languages']} Languages",
        description=(
            "Index of the 100 most-starred GitHub repositories for 30 programming "
            "languages, with entry star counts, medians and JSONL downloads."
        ),
        canonical=f"{C.BASE_URL}/languages/index.html",
        body=body, jsonld=jsonld,
        updated_line=f"Data refreshed {ctx['datetime_long']}",
        active="languages/index.html",
    )


def page_language(ctx, key):
    info = ctx["langs"][key]
    repos = info["repos"]
    url = f"{C.BASE_URL}/languages/{info['slug']}.html"
    first = repos[0]
    lic_share = info["top_license_n"]

    intro = (
        f"GitHub reports {fmt(info['total_count'])} repositories whose detected "
        f"primary language is {info['display']}. The {len(repos)} most-starred of them are "
        f"listed below, ranked by <code>stargazers_count</code>. "
        f"<a href='{esc(first.get('html_url', ''))}'>{esc(first['full_name'])}</a> leads "
        f"with {fmt(info['max_stars'])} stars, and the bar for 100th place is "
        f"{fmt(info['min_stars'])} stars. The median repository in this top 100 has "
        f"{fmt(info['median_stars'])} stars, and the most common licence is "
        f"{esc(info['top_license'])} ({lic_share} of {len(repos)} repositories)."
    )

    faq = []
    if len(repos) >= 3:
        second, third = repos[1], repos[2]
        faq = [
        (
            f"What is the most-starred {info['display']} repository on GitHub?",
            f"{esc(first['full_name'])} is the most-starred {info['display']} repository "
            f"with {fmt(info['max_stars'])} stars as of {ctx['date_long']}, ahead of "
            f"{esc(second['full_name'])} ({fmt(second['stargazers_count'])}) and "
            f"{esc(third['full_name'])} ({fmt(third['stargazers_count'])}).",
        ),
        (
            f"How many {info['display']} repositories are on GitHub?",
            f"GitHub reports {fmt(info['total_count'])} public repositories whose detected "
            f"primary language is {info['display']}. Top100 ranks the {len(repos)} "
            f"most-starred of them; {len(repos)}th place currently needs "
            f"{fmt(info['min_stars'])} stars.",
        ),
        (
            f"How do I download the top 100 {info['display']} repositories as JSON?",
            f"Download `data/JSONL/{key}.jsonl` \u2014 {len(repos)} lines, each the "
            "complete GitHub Search API object for one repository, including topics, "
            "licence, every count and every timestamp. A readable Markdown table of the "
            "same ranking is also published.",
        ),
        ]

    others = [
        k for k in ctx["langs"] if k != key
    ][:8]
    lang_snippet = code_block(
        f"curl -sSL -o {key}.jsonl \\\n"
        f"  {jsonl_url(key)}\n"
        "jq -r '.full_name + \"  \" + (.stargazers_count|tostring)' "
        f"{key}.jsonl | head -10"
    )
    other_items = "".join(
        f"<li><a href='{ctx['langs'][k]['slug']}.html'>Top 100 "
        f"{esc(ctx['langs'][k]['display'])} repositories</a></li>"
        for k in others
    )

    body = f"""
<h1>Top 100 {esc(info['display'])} repositories on GitHub, ranked by stars</h1>
<p class="lead">{esc(info['note'])}</p>
<p>{intro}</p>
<ul class="facts">
<li><b>100</b> repositories ranked</li>
<li><b>{fmt(info['max_stars'])}</b> stars for #1</li>
<li><b>{fmt(info['min_stars'])}</b> stars to enter the top 100</li>
<li><b>{fmt(info['median_stars'])}</b> median stars in the top 100</li>
<li><b>{fmt(info['total_count'])}</b> repositories GitHub reports</li>
<li><b>{round(info['size_bytes'] / 1024, 1)} KB</b> JSONL file</li>
</ul>

<h2>The 100 most-starred {esc(info['display'])} repositories</h2>
{repo_table(repos, caption=f"The 100 most-starred {info['display']} repositories on GitHub, refreshed {ctx['datetime_long']}. Ranked by stars.")}
<p class="small muted">Fork counts include open pull requests in
<code>open_issues_count</code>, because that is how GitHub's API reports it.
Descriptions are truncated to 140 characters; the full text is in the JSONL
download.</p>

<h2>Download the {esc(info['display'])} data</h2>
<ul>
<li><a href="{jsonl_url(key)}">JSONL &mdash; raw GitHub Search API objects</a>
({round(info['size_bytes'] / 1024, 1)} KB, {len(repos)} lines)</li>
<li><a href="{md_file_url(key)}">Markdown table</a> of the same ranking</li>
<li><a href="{C.TREE_URL}/data/JSONL">All {ctx['languages']} JSONL files</a></li>
</ul>
{lang_snippet}

<h2>How this list is built</h2>
<p>A single GitHub Search API request per language &mdash;
<code>?q=language:{esc(key)}&amp;sort=stars&amp;order=desc&amp;per_page=100</code>
&mdash; refreshed hourly by a scheduled GitHub Actions workflow and committed back to
the repository. The records are never reshaped: every field GitHub returned is
preserved. The <a href="../methodology.html">methodology page</a> covers the query,
the rate limits, the fields the Search API omits and the known limitations, and the
<a href="../dataset.html">field reference</a> documents every JSON key.</p>

<h2>Frequently asked questions</h2>
{faq_html(faq)}

<h2>Other languages</h2>
<ul>
{other_items}
<li><a href="index.html">All {ctx['languages']} languages &rarr;</a></li>
</ul>
"""
    jsonld = [
        {"@context": "https://schema.org", "@graph": [
            jsonld_webpage(ctx, name=f"Top 100 {info['display']} repositories on GitHub, ranked by stars",
                           description=f"The 100 most-starred {info['display']} repositories on GitHub, refreshed hourly, with a JSONL download.",
                           page_url=url),
            jsonld_breadcrumb([
                ("Top100", f"{C.BASE_URL}/"),
                ("Languages", f"{C.BASE_URL}/languages/index.html"),
                (f"Top 100 {info['display']}", url),
            ], url),
            jsonld_dataset(ctx, key=key),
            jsonld_itemlist(repos, url, f"Top 100 {info['display']} repositories by stars"),
            jsonld_faq(faq, url),
        ]},
    ]
    return html_page(
        ctx=ctx, prefix="../",
        title=f"Top 100 {info['display']} Repositories by Stars ({ctx['date_short']})",
        description=(
            f"The 100 most-starred {info['display']} repositories on GitHub, ranked by "
            f"stars and refreshed hourly. Includes stars, forks, open issues, licence and "
            f"last push, plus a free JSONL download of the raw GitHub API data."
        ),
        canonical=url, body=body, jsonld=jsonld,
        updated_line=f"Data refreshed {ctx['datetime_long']}",
        active="languages/index.html",
    )


def page_methodology(ctx):
    url = f"{C.BASE_URL}/methodology.html"
    sections = "\n".join(
        f"<h2>{esc(title)}</h2>\n{body}" for title, body in C.METHODOLOGY["sections"]
    )
    body = f"""
<h1>{esc(C.METHODOLOGY['h1'])}</h1>
<p class="lead">Everything on this site is the output of one script, one workflow and
one API endpoint. This page documents exactly what happens, so that any number here
can be reproduced or challenged.</p>
{sections}
{C.METHODOLOGY['closing']}
"""
    jsonld = [
        {"@context": "https://schema.org", "@graph": [
            jsonld_webpage(ctx, name=C.METHODOLOGY["h1"], description=C.METHODOLOGY["description"],
                           page_url=url, page_type="TechArticle"),
            jsonld_breadcrumb([
                ("Top100", f"{C.BASE_URL}/"),
                ("Methodology", url),
            ], url),
            jsonld_software(ctx),
        ]},
    ]
    return html_page(
        ctx=ctx, prefix="", title=C.METHODOLOGY["title"], description=C.METHODOLOGY["description"],
        canonical=url, body=body, jsonld=jsonld,
        updated_line=f"Data refreshed {ctx['datetime_long']}",
        active="methodology.html",
    )


def page_dataset(ctx):
    url = f"{C.BASE_URL}/dataset.html"
    file_rows = []
    for key, info in ctx["langs"].items():
        file_rows.append(
            f"<tr><td><a href='languages/{info['slug']}.html'>{esc(info['display'])}</a></td>"
            f"<td><code>data/JSONL/{key}.jsonl</code></td>"
            f"<td class='num'>{info['n']}</td>"
            f"<td class='num'>{round(info['size_bytes'] / 1024, 1)} KB</td>"
            f"<td><a href='{jsonl_url(key)}'>download</a></td></tr>"
        )
    field_rows = []
    for name, ftype, desc in C.DATASET_FIELDS:
        if ftype is None:
            field_rows.append(
                f"<tr><th colspan='3'>{esc(name)}</th></tr>"
            )
        else:
            field_rows.append(
                f"<tr><td><code>{esc(name)}</code></td><td>{esc(ftype)}</td>"
                f"<td>{md_inline(desc)}</td></tr>"
            )
    example = ctx["langs"].get("python") or next(iter(ctx["langs"].values()))
    sample = json.dumps(example["repos"][0], ensure_ascii=False, indent=2)
    sample_lines = sample.splitlines()
    if len(sample_lines) > 40:
        sample = "\n".join(sample_lines[:40]) + "\n  … (truncated for display)"
    body = f"""
<h1>Dataset field reference: every field in the Top100 JSONL files</h1>
<p class="lead">The Top100 dataset is {ctx['languages']} newline-delimited JSON files
&mdash; {fmt(ctx['records'])} GitHub repository records in total &mdash; where every
line is the complete, untouched repository object returned by GitHub's Search API.</p>
{C.DATASET_INTRO}

<h2>Files</h2>
<div class='tablewrap'><table>
<caption>One file per language, 100 records each. Total {round(ctx['jsonl_bytes'] / 1_048_576, 1)} MB.</caption>
<thead><tr><th>Language</th><th>File</th><th class='num'>Records</th>
<th class='num'>Size</th><th>Download</th></tr></thead>
<tbody>
{chr(10).join(file_rows)}
</tbody>
</table></div>

<h2>Every field, documented</h2>
<div class='tablewrap'><table>
<caption>Fields of the GitHub Search API repository object, in the order GitHub returns them.</caption>
<thead><tr><th>Field</th><th>Type</th><th>What it is</th></tr></thead>
<tbody>
{chr(10).join(field_rows)}
</tbody>
</table></div>
{C.DATASET_MISSING}

<h2>Load it</h2>
{C.DATASET_LOADING}

<h2>Example record</h2>
<p>The first line of <code>data/JSONL/{esc(example['key'])}.jsonl</code>, pretty-printed:</p>
<pre><code>{esc(sample)}</code></pre>

<h2>Licensing and attribution</h2>
<p>The repository metadata is GitHub's, served through GitHub's public API, and each
listed project keeps its own licence &mdash; check the <code>license</code> field
before reusing anyone's code. The collection script, the generated tables and this
website are published under the MIT licence in the
<a href="{C.BLOB_URL}/LICENSE">repository</a>. If you republish the data,
link back here and credit GitHub as the source.</p>
"""
    jsonld = [
        {"@context": "https://schema.org", "@graph": [
            jsonld_webpage(ctx, name="Dataset field reference: every field in the Top100 JSONL files",
                           description="Every field of the GitHub Search API repository object in the Top100 JSONL dataset, documented, with download and query examples.",
                           page_url=url),
            jsonld_breadcrumb([
                ("Top100", f"{C.BASE_URL}/"),
                ("Dataset", url),
            ], url),
            jsonld_dataset(ctx),
        ]},
    ]
    return html_page(
        ctx=ctx, prefix="", title="GitHub Repository Metadata JSONL Dataset — Field Reference & Download",
        description=(
            "Download 30 JSONL files of raw GitHub repository metadata — 3,000 records, "
            "one complete Search API object per line — with a documented reference for "
            "every field."
        ),
        canonical=url, body=body, jsonld=jsonld,
        updated_line=f"Data refreshed {ctx['datetime_long']}",
        active="dataset.html",
    )


def page_compare(ctx):
    url = f"{C.BASE_URL}/compare.html"
    rows = "\n".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in C.COMPARISON["rows"]
    )
    use_top = "\n".join(f"<li>{item}</li>" for item in C.COMPARISON["use_top100"])
    use_other = "\n".join(f"<li>{item}</li>" for item in C.COMPARISON["use_other"])
    body = f"""
<h1>{esc(C.COMPARISON['h1'])}</h1>
{C.COMPARISON['intro']}
<div class='tablewrap'><table>
<caption>GitHub ranking and dataset sources, checked September 2026.</caption>
<thead><tr><th>Source</th><th>What you get</th><th>Format</th><th>Refresh</th>
<th>Per-language top 100</th><th>Machine-readable export</th></tr></thead>
<tbody>
{rows}
</tbody>
</table></div>
<h2>Use Top100 when&hellip;</h2>
<ul>
{use_top}
</ul>
<h2>Use something else when&hellip;</h2>
<ul>
{use_other}
</ul>
{C.COMPARISON['closing']}
"""
    jsonld = [
        {"@context": "https://schema.org", "@graph": [
            jsonld_webpage(ctx, name=C.COMPARISON["h1"], description=C.COMPARISON["description"],
                           page_url=url, page_type="TechArticle"),
            jsonld_breadcrumb([
                ("Top100", f"{C.BASE_URL}/"),
                ("Comparison", url),
            ], url),
            jsonld_software(ctx),
            jsonld_dataset(ctx),
        ]},
    ]
    return html_page(
        ctx=ctx, prefix="", title=C.COMPARISON["title"], description=C.COMPARISON["description"],
        canonical=url, body=body, jsonld=jsonld,
        updated_line=f"Data refreshed {ctx['datetime_long']}",
        active="compare.html",
    )


def page_faq(ctx):
    url = f"{C.BASE_URL}/faq.html"
    entries = C.faq_entries(ctx) + C.extra_faq_entries(ctx)
    body = f"""
<h1>Frequently asked questions about the Top100 dataset</h1>
<p class="lead">Direct answers to the questions people actually ask about GitHub
repository rankings, JSONL datasets and scheduled data collection. The first eight
also appear on the <a href="index.html#faq">homepage</a>.</p>
{faq_html(entries, level=2)}
<h2>Still stuck?</h2>
<p>Open an issue on the <a href="{C.REPO_URL}/issues">GitHub repository</a>, or read
the <a href="methodology.html">methodology</a> and
<a href="dataset.html">field reference</a> pages first &mdash; they answer most
implementation questions.</p>
"""
    jsonld = [
        {"@context": "https://schema.org", "@graph": [
            jsonld_webpage(ctx, name="FAQ: top 100 GitHub repositories, JSONL dataset and GitHub Actions automation",
                           description="Sixteen questions with direct answers about the Top100 GitHub repository ranking dataset.",
                           page_url=url),
            jsonld_breadcrumb([
                ("Top100", f"{C.BASE_URL}/"),
                ("FAQ", url),
            ], url),
            jsonld_faq(entries, url),
        ]},
    ]
    return html_page(
        ctx=ctx, prefix="", title="FAQ: Top 100 GitHub Repositories, JSONL Dataset & GitHub Actions Automation",
        description=(
            "Sixteen questions with direct answers: where to find a top 100 GitHub "
            "repositories list, how to download GitHub repo metadata as JSONL, and how to "
            "automate collection with GitHub Actions."
        ),
        canonical=url, body=body, jsonld=jsonld,
        updated_line=f"Data refreshed {ctx['datetime_long']}",
        active="faq.html",
    )


def page_404(ctx):
    # A 404 is served at whatever depth the broken URL had, so every link on
    # this page must be absolute from the site root.
    p = "/top100/"
    body = f"""
<h1>404 &mdash; page not found</h1>
<p>That URL does not exist on this site. The pages that do:</p>
<ul>
<li><a href="{p}index.html">Homepage</a> &mdash; the current top 10 and every language</li>
<li><a href="{p}languages/index.html">All languages</a> &mdash; {ctx['languages']} top 100 lists</li>
<li><a href="{p}dataset.html">Dataset &amp; field reference</a> &mdash; download the JSONL</li>
<li><a href="{p}methodology.html">Methodology</a> &mdash; how the data is collected</li>
<li><a href="{p}compare.html">Comparison</a> &mdash; Top100 vs other ranking sources</li>
<li><a href="{p}faq.html">FAQ</a> &mdash; sixteen answered questions</li>
</ul>
<p>If you followed a link from elsewhere, the data refresh may have renamed a file:
the canonical list of data files is in the
<a href="{C.TREE_URL}/data">repository</a>.</p>
"""
    return html_page(
        ctx=ctx, prefix=p, title="404 — page not found | Top100",
        description="That page does not exist. Links to every page on Top100.",
        canonical=f"{C.BASE_URL}/404.html", body=body, jsonld=[],
        active=None,
    )


# ---------------------------------------------------------------------------
# Non-HTML artifacts
# ---------------------------------------------------------------------------

def build_sitemap(ctx):
    urls = [("", "1.0", "hourly")]
    urls.append(("languages/index.html", "0.9", "hourly"))
    for key, info in ctx["langs"].items():
        urls.append((f"languages/{info['slug']}.html", "0.8", "hourly"))
    for page, priority in [
        ("dataset.html", "0.8"), ("methodology.html", "0.7"),
        ("compare.html", "0.7"), ("faq.html", "0.7"),
    ]:
        urls.append((page, priority, "weekly"))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, priority, changefreq in urls:
        loc = f"{C.BASE_URL}/{path}" if path else f"{C.BASE_URL}/"
        lines.append(
            f"<url><loc>{esc(loc)}</loc><lastmod>{ctx['iso_date']}</lastmod>"
            f"<changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>"
        )
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def build_robots(ctx):
    return f"""# Top100 — https://havaianasdestruido.github.io/top100/
# Everything here is public, static and meant to be read by humans and agents alike.

User-agent: *
Allow: /

# AI assistants and crawlers are explicitly welcome.
User-agent: GPTBot
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: Claude-Web
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: Applebot-Extended
Allow: /

User-agent: Meta-ExternalAgent
Allow: /

User-agent: Amazonbot
Allow: /

User-agent: cohere-ai
Allow: /

User-agent: CCBot
Allow: /

Sitemap: {C.BASE_URL}/sitemap.xml
"""


def build_llms_txt(ctx):
    lines = [
        "# Top100",
        "",
        "> The 100 most-starred GitHub repositories for 30 programming languages, "
        "rebuilt every hour from the GitHub Search API and published as raw "
        "newline-delimited JSON you can download without an API key.",
        "",
        "Top100 answers \"what are the top GitHub repositories by stars right now?\" "
        f"for {ctx['languages']} languages. Every page carries the timestamp of the "
        "refresh that produced it. Each JSONL line is the complete, unmodified "
        "repository object GitHub returned: owner, licence, topics, every count and "
        "every timestamp.",
        "",
        "## Start here",
        "",
        f"- [Homepage]({C.BASE_URL}/index.html): the current overall top 10, the "
        "language index, star-threshold statistics and the FAQ",
        f"- [All {ctx['languages']} languages]({C.BASE_URL}/languages/index.html): "
        "every top 100 list with entry star counts and medians",
        "",
        "## Top 100 lists by language",
        "",
    ]
    for key, info in ctx["langs"].items():
        lines.append(
            f"- [Top 100 {info['display']} repositories]"
            f"({C.BASE_URL}/languages/{info['slug']}.html): led by "
            f"{info['repos'][0]['full_name']} with {fmt(info['max_stars'])} stars"
        )
    lines += [
        "",
        "## Reference",
        "",
        f"- [Methodology]({C.BASE_URL}/methodology.html): the exact Search API query, "
        "refresh cadence, rate limits and known limitations",
        f"- [Dataset field reference]({C.BASE_URL}/dataset.html): every field in the "
        "JSONL files, plus download and DuckDB/pandas/jq examples",
        f"- [Comparison]({C.BASE_URL}/compare.html): Top100 vs GitHub Trending, "
        "gitstar-ranking.com, EvanLi/Github-Ranking, OSS Insight, Star History, "
        "GH Archive and BigQuery",
        f"- [FAQ]({C.BASE_URL}/faq.html): sixteen questions with direct answers",
        "",
        "## Data",
        "",
        f"- JSONL files (30 files, 100 records each, {fmt(ctx['records'])} total): "
        f"{C.TREE_URL}/data/JSONL",
        f"- Raw download pattern: {C.RAW_URL}/data/JSONL/python.jsonl",
        f"- Markdown tables: {C.TREE_URL}/data",
        f"- Update feed (RSS): {C.BASE_URL}/feed.xml",
        "",
        "## Notes",
        "",
        f"- Refreshed hourly by a scheduled GitHub Actions workflow; the data is "
        f"GitHub API output and every repository keeps its own licence.",
        f"- Source code and workflow: {C.REPO_URL}",
        "- No JavaScript, no tracking, no cookies, no external requests.",
        "",
    ]
    return "\n".join(lines)


def build_llms_full(ctx):
    out = [
        "# Top100 — full content",
        "",
        f"> Generated {ctx['datetime_long']} from the live dataset.",
        "",
        "## What this is",
        "",
        f"Top100 publishes the 100 most-starred GitHub repositories for "
        f"{ctx['languages']} programming languages, rebuilt hourly from the GitHub "
        f"Search API. The dataset is {fmt(ctx['records'])} newline-delimited JSON "
        f"records ({round(ctx['jsonl_bytes'] / 1_048_576, 1)} MB) in which every line "
        f"is the complete, unmodified repository object GitHub returned.",
        "",
        "## The ten most-starred repositories right now",
        "",
        "| # | Repository | Language | Stars |",
        "| --- | --- | --- | --- |",
    ]
    for i, r in enumerate(ctx["top_overall"], start=1):
        out.append(
            f"| {i} | {r['full_name']} | {r.get('language') or '—'} | "
            f"{fmt(r['stargazers_count'])} |"
        )
    out += [
        "",
        "## Statistics by language",
        "",
        "| Language | Leader | Stars | Stars to enter top 100 | Median in top 100 | "
        "Repos GitHub reports |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for key, info in ctx["langs"].items():
        out.append(
            f"| {info['display']} | {info['repos'][0]['full_name']} | "
            f"{fmt(info['max_stars'])} | {fmt(info['min_stars'])} | "
            f"{fmt(info['median_stars'])} | {fmt(info['total_count'])} |"
        )
    out += [
        "",
        "## Top five repositories per language",
        "",
    ]
    for key, info in ctx["langs"].items():
        out.append(f"### Top 100 {info['display']} repositories")
        out.append("")
        for i, r in enumerate(info["repos"][:5], start=1):
            desc = truncate(r.get("description"), 90)
            out.append(
                f"{i}. {r['full_name']} — {fmt(r['stargazers_count'])} stars"
                + (f" — {desc}" if desc else "")
            )
        out.append(
            f"- Full list: {C.BASE_URL}/languages/{info['slug']}.html"
        )
        out.append(
            f"- JSONL: {C.RAW_URL}/data/JSONL/{key}.jsonl"
        )
        out.append("")
    out += ["## Frequently asked questions", ""]
    for q, a in C.faq_entries(ctx) + C.extra_faq_entries(ctx):
        out.append(f"### {q}")
        out.append("")
        out.append(md_plain(a))
        out.append("")
    out += [
        "## Methodology in one paragraph",
        "",
        "One GitHub Search API request per language: "
        "`GET /search/repositories?q=language:<name>&sort=stars&order=desc&per_page=100`. "
        "A scheduled GitHub Actions workflow runs it for all 30 languages every hour, "
        "writes the raw JSONL and a Markdown table per language, rebuilds this site and "
        "commits everything back to the repository. No per-repository calls are made, so "
        "a full refresh costs 30 Search API requests. Fields only available from the "
        "single-repository endpoint (subscribers_count, network_count, parent/source) "
        "are absent unless ENRICH_WITH_REPO_DETAILS is enabled.",
        "",
        f"Full details: {C.BASE_URL}/methodology.html",
        "",
        "## Links",
        "",
        f"- Homepage: {C.BASE_URL}/index.html",
        f"- All languages: {C.BASE_URL}/languages/index.html",
        f"- Dataset: {C.BASE_URL}/dataset.html",
        f"- Comparison: {C.BASE_URL}/compare.html",
        f"- FAQ: {C.BASE_URL}/faq.html",
        f"- Repository: {C.REPO_URL}",
        "",
    ]
    return "\n".join(out)


def build_feed(ctx):
    items = []
    for key, info in ctx["langs"].items():
        top = info["repos"][0]
        desc = (
            f"Top 100 {info['display']} repositories, refreshed {ctx['datetime_long']}. "
            f"{top['full_name']} leads with {fmt(top['stargazers_count'])} stars; "
            f"{fmt(info['min_stars'])} stars are needed to reach 100th place. "
            f"Full table: {C.BASE_URL}/languages/{info['slug']}.html"
        )
        items.append(
            f"<item><title>Top 100 {esc(info['display'])} repositories updated: "
            f"{esc(top['full_name'])} leads with {fmt(top['stargazers_count'])} stars</title>"
            f"<link>{C.BASE_URL}/languages/{info['slug']}.html</link>"
            f"<guid isPermaLink=\"true\">{C.BASE_URL}/languages/{info['slug']}.html</guid>"
            f"<pubDate>{ctx['rfc822']}</pubDate>"
            f"<description>{esc(desc)}</description></item>"
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<title>Top100 — GitHub top 100 repositories by language</title>
<link>{C.BASE_URL}/</link>
<description>Hourly refreshes of the 100 most-starred GitHub repositories for {ctx['languages']} programming languages. Each item is a language list whose contents change on every refresh.</description>
<language>en</language>
<lastBuildDate>{ctx['rfc822']}</lastBuildDate>
<atom:link href="{C.BASE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
{chr(10).join(items)}
</channel>
</rss>
"""


def update_readme_leaders(ctx):
    """Refresh the "current leaders" table in README.md from the live data, so the
    repository's own front page never shows stale numbers. The table lives between
    HTML comment markers and is regenerated on every build."""
    path = ROOT / "README.md"
    if not path.exists():
        return None
    src = path.read_text(encoding="utf-8")
    start = src.find("<!-- LEADERS:START -->")
    end = src.find("<!-- LEADERS:END -->")
    if start == -1 or end == -1 or end < start:
        return None

    lines = [
        "| # | Repository | Language | Stars |",
        "| --- | --- | --- | --- |",
    ]
    for i, r in enumerate(ctx["top_overall"][:10], start=1):
        lines.append(
            f"| {i} | [{r['full_name']}]({r.get('html_url', '')}) | "
            f"{r.get('language') or '—'} | {fmt(r['stargazers_count'])} |"
        )
    block = (
        "\n".join(lines)
        + f"\n\nRefreshed {ctx['datetime_long']} — these ten are the most-starred "
        "repositories across every language Top100 tracks."
    )
    new_src = src[:start] + "<!-- LEADERS:START -->\n" + block + "\n" + src[end:]
    if new_src == src:
        return path
    path.write_text(new_src, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not DATA.exists():
        print("No data/ directory found.", file=sys.stderr)
        return 1
    langs = load_data()
    if not langs:
        print("No JSONL data found in data/JSONL/.", file=sys.stderr)
        return 1
    ctx = build_context(langs)

    written = []
    written.append(write("index.html", page_index(ctx)))
    written.append(write("languages/index.html", page_languages_index(ctx)))
    for key in langs:
        written.append(write(f"languages/{langs[key]['slug']}.html", page_language(ctx, key)))
    written.append(write("methodology.html", page_methodology(ctx)))
    written.append(write("dataset.html", page_dataset(ctx)))
    written.append(write("compare.html", page_compare(ctx)))
    written.append(write("faq.html", page_faq(ctx)))
    written.append(write("404.html", page_404(ctx)))
    written.append(write("assets/style.css", C.CSS))
    written.append(write("sitemap.xml", build_sitemap(ctx)))
    written.append(write("robots.txt", build_robots(ctx)))
    written.append(write("llms.txt", build_llms_txt(ctx)))
    written.append(write("llms-full.txt", build_llms_full(ctx)))
    written.append(write("feed.xml", build_feed(ctx)))
    readme = update_readme_leaders(ctx)
    if readme is not None:
        written.append(readme)

    total = sum(p.stat().st_size for p in written)
    print(f"Built {len(written)} files ({total / 1024:.0f} KB) from "
          f"{ctx['records']} records across {ctx['languages']} languages.")
    print(f"Data timestamp: {ctx['datetime_long']}")
    for q, a in C.faq_entries(ctx):
        n = words(a)
        flag = "" if 40 <= n <= 70 else "  <-- outside 40-70 words"
        print(f"  FAQ ({n:2d} words): {q}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
