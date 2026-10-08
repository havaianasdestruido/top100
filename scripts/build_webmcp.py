#!/usr/bin/env python3
"""
Generate every WebMCP artifact for the Top100 site.

Three files come out of here:

    data/search-index.json    compact records for all 3,000 repositories, used
                              by search_repositories / get_repository /
                              compare_repositories (loaded lazily, same-origin)
    data/webmcp-context.json  the site's own prose — FAQ, methodology, dataset
                              fields, comparisons — for the documentation tools
    data/webmcp-manifest.json the machine-readable tool catalogue: every tool's
                              name, description, JSON Schema and annotations,
                              plus data-file sizes and SHA-256 checksums

and one HTML fragment: the JSON block each page embeds so its tools can answer
without any network access at all (the page's own rows, the language index and
the site facts).

Everything here is deterministic: the same data directory always produces
byte-identical output apart from the timestamp, so a diff on this repository
shows real changes only.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import quote, urlparse

import site_content as C
from webmcp_catalog import BUDGET, load_tools

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SEARCH_INDEX_SCHEMA = "top100.search-index/1"
CONTEXT_SCHEMA = "top100.webmcp-context/1"
MANIFEST_SCHEMA = "top100.webmcp/1"
PAGE_DATA_SCHEMA = "top100.webmcp-page/1"

MAX_DESCRIPTION = 140
MAX_TOPICS = 6
MAX_NOTE = 200

TAG_RE = re.compile(r"<[^>]+>")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
CODE_RE = re.compile(r"`([^`]+)`")
WS_RE = re.compile(r"[ \t]{2,}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def jsonl_url(key: str) -> str:
    return f"{C.RAW_URL}/data/JSONL/{quote(key, safe='')}.jsonl"


def md_file_url(key: str) -> str:
    return f"{C.BLOB_URL}/data/TOP_{quote(key.upper(), safe='')}_100.md"


def html_to_text(value: str) -> str:
    """Flatten the site's own prose into single-paragraph plain text."""
    text = str(value or "")
    text = re.sub(r"<pre><code>(.*?)</code></pre>", r"\1", text, flags=re.S)
    text = re.sub(r"<(p|li|br|div|h[1-6])[^>]*>", "\n", text)
    text = LINK_RE.sub(r"\1", text)
    text = CODE_RE.sub(r"\1", text)
    text = TAG_RE.sub("", text)
    text = html.unescape(text)
    text = text.replace("&mdash;", "-").replace("&middot;", "-")
    text = WS_RE.sub(" ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def slugify(value: str, fallback: str = "section") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return slug[:60] or fallback


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def license_of(repo) -> str:
    return ((repo.get("license") or {}).get("spdx_id") or "NOASSERTION")


def pushed_of(repo) -> str:
    return str(repo.get("pushed_at") or "")[:10]


def topics_of(repo, limit: int = MAX_TOPICS):
    topics = repo.get("topics") or []
    if not isinstance(topics, list):
        return []
    return [str(t)[:40] for t in topics[:limit]]


def truncate(value, limit: int = MAX_DESCRIPTION) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "\u2026"


def embed_json(payload) -> str:
    """Serialise for an HTML <script> block: `<` is escaped so a string can
    never close the element early, and the payload stays valid JSON."""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003c")


def dump_json(payload, compact: bool = False) -> str:
    """Serialise a data artifact. Compact output is used for the search index,
    which nobody reads by hand; the manifest and context file are indented so
    that a committed diff shows real changes."""
    if compact:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    return json.dumps(payload, ensure_ascii=False, indent=1) + "\n"


# ---------------------------------------------------------------------------
# 1. The language index shared by every page's tools
# ---------------------------------------------------------------------------

def language_records(ctx) -> list:
    out = []
    for key, info in ctx["langs"].items():
        top = info["repos"][0] if info["repos"] else {}
        out.append({
            "key": key,
            "display": info["display"],
            "slug": info["slug"],
            "note": truncate(info["note"], MAX_NOTE),
            "leader": top.get("full_name", ""),
            "leader_url": top.get("html_url", ""),
            "max_stars": info["max_stars"],
            "min_stars": info["min_stars"],
            "median_stars": info["median_stars"],
            "total_count": info["total_count"] or 0,
            "size_bytes": info["size_bytes"],
            "sha256": info["sha256"],
            "top_license": info["top_license"],
            "top_license_n": info["top_license_n"],
            "jsonl": jsonl_url(key),
            "markdown": md_file_url(key),
        })
    return out


def repo_records(repos) -> list:
    out = []
    for rank, repo in enumerate(repos, start=1):
        out.append({
            "rank": rank,
            "full_name": repo.get("full_name", ""),
            "url": repo.get("html_url", ""),
            "language": repo.get("language") or "",
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "open_issues": repo.get("open_issues_count", 0),
            "license": license_of(repo),
            "pushed_at": pushed_of(repo),
            "topics": topics_of(repo),
            "description": truncate(repo.get("description")),
            "archived": bool(repo.get("archived")),
        })
    return out


# ---------------------------------------------------------------------------
# 2. The JSON block embedded in every page
# ---------------------------------------------------------------------------

def relative_base(page_path: str) -> str:
    """The prefix that gets from a page's directory back to the site root."""
    parent = Path(page_path).parent
    depth = 0 if str(parent) == "." else len(parent.parts)
    return "../" * depth


def absolute_base() -> str:
    """The site's path on its host, for 404.html — which is served at whatever
    depth the broken URL had, so relative paths cannot work there."""
    path = urlparse(C.BASE_URL).path.rstrip("/")
    return (path or "") + "/"


def page_data(ctx, *, page_type, page_path, language=None, repos=None, faq=None,
              absolute_links=False) -> dict:
    """Everything the tools need to answer without touching the network."""
    payload = {
        "schema": PAGE_DATA_SCHEMA,
        "as_of": ctx["meta"].get("fetched_at", ""),
        "site": {
            "name": "Top100",
            "base_url": C.BASE_URL,
            "repo_url": C.REPO_URL,
            "records": ctx["records"],
            "languages": ctx["languages"],
            "jsonl_bytes": ctx["jsonl_bytes"],
            "data_as_of": ctx["meta"].get("data_as_of", ""),
            "fetched_at": ctx["meta"].get("fetched_at", ""),
            "source": "GitHub Search API",
        },
        "page": {
            "type": page_type,
            "path": page_path,
            "url": f"{C.BASE_URL}/{page_path}".replace("index.html", ""),
            "language": language,
            # Where the page's own data files live, and — for 404.html only —
            # the site-absolute base its links must use.
            "data_base": absolute_base() if absolute_links else relative_base(page_path),
            "absolute_base": absolute_base() if absolute_links else "",
        },
        "languages": language_records(ctx),
        "repos": repo_records(repos or []),
        "faq": [{"q": html_to_text(q), "a": html_to_text(a)} for q, a in (faq or [])],
    }
    return payload


# ---------------------------------------------------------------------------
# 3. The lazily-loaded search index
# ---------------------------------------------------------------------------

def build_search_index(ctx) -> dict:
    rows = []
    for key, info in ctx["langs"].items():
        for repo in sorted(info["repos"], key=lambda r: r.get("stargazers_count", 0), reverse=True):
            rows.append([
                repo.get("full_name", ""),
                key,
                int(repo.get("stargazers_count", 0) or 0),
                int(repo.get("forks_count", 0) or 0),
                int(repo.get("open_issues_count", 0) or 0),
                pushed_of(repo),
                license_of(repo),
                topics_of(repo),
                truncate(repo.get("description")),
            ])
    return {
        "schema": SEARCH_INDEX_SCHEMA,
        "generated_at": ctx["meta"].get("fetched_at", ""),
        "fields": ["full_name", "language", "stars", "forks", "open_issues",
                   "pushed_at", "license", "topics", "description"],
        "count": len(rows),
        "repos": rows,
    }


# ---------------------------------------------------------------------------
# 4. The prose the documentation tools serve
# ---------------------------------------------------------------------------

def build_context(ctx) -> dict:
    docs = []

    for title, body in C.METHODOLOGY["sections"]:
        docs.append({
            "kind": "methodology",
            "id": slugify(title),
            "title": html_to_text(title),
            "text": truncate(html_to_text(body), 900),
        })
    docs.append({
        "kind": "methodology",
        "id": "summary",
        "title": "Overview",
        "text": truncate(html_to_text(C.METHODOLOGY["description"] + " " +
                                     C.METHODOLOGY["closing"]), 900),
    })

    group = ""
    for name, ftype, desc in C.DATASET_FIELDS:
        if ftype is None:
            group = html_to_text(name)
            continue
        docs.append({
            "kind": "field",
            "id": html_to_text(name),
            "type": html_to_text(ftype),
            "group": group,
            "text": truncate(html_to_text(desc), 300),
        })

    rows = C.COMPARISON.get("rows", [])
    for row in rows:
        if not row:
            continue
        name = html_to_text(row[0])
        docs.append({
            "kind": "comparison",
            "id": slugify(name),
            "title": name,
            "text": truncate(
                "What it covers: " + html_to_text(row[1]) +
                ". Format: " + html_to_text(row[2]) +
                ". Freshness: " + html_to_text(row[3]) +
                ". Per-language coverage: " + html_to_text(row[4]) +
                ". Data export: " + html_to_text(row[5]) + ".", 600),
        })
    docs.append({
        "kind": "comparison",
        "id": "when-top100",
        "title": "When to use Top100",
        "text": truncate(html_to_text(" ".join(C.COMPARISON.get("use_top100", []))), 600),
    })
    docs.append({
        "kind": "comparison",
        "id": "when-something-else",
        "title": "When to use another source",
        "text": truncate(html_to_text(" ".join(C.COMPARISON.get("use_other", []))), 600),
    })

    faq = []
    seen = set()
    for question, answer in C.faq_entries(ctx) + C.extra_faq_entries(ctx):
        text = html_to_text(question)
        if text in seen:
            continue
        seen.add(text)
        faq.append({"q": text, "a": truncate(html_to_text(answer), 900)})

    return {
        "schema": CONTEXT_SCHEMA,
        "generated_at": ctx["meta"].get("fetched_at", ""),
        "faq": faq,
        "docs": docs,
    }


# ---------------------------------------------------------------------------
# 5. The machine-readable tool manifest
# ---------------------------------------------------------------------------

def build_manifest(ctx, tools, data_files=None) -> dict:
    return {
        "schema": MANIFEST_SCHEMA,
        "generated_at": ctx["meta"].get("fetched_at", ""),
        "site": {
            "name": "Top100",
            "url": C.BASE_URL + "/",
            "description": (
                "The 100 most-starred GitHub repositories for 30 programming languages, "
                "rebuilt hourly from the GitHub Search API and published as raw JSONL."
            ),
            "repository": C.REPO_URL,
            "license": "MIT",
            "data_license": "GitHub API output; each listed project keeps its own licence",
        },
        "runtime": {
            "standard": "WebMCP (Web Model Context Protocol)",
            "spec": "https://webmachinelearning.github.io/webmcp/",
            "entry_point": "document.modelContext",
            "core": "assets/webmcp-core.js",
            "tools": "assets/webmcp-tools.js",
            "native_first": True,
            "polyfill_included": True,
            "polyfill_baseline": "Chrome 126, Firefox 126, Safari 18",
            "requires_secure_context": True,
            "permissions_policy": "tools=(self)",
            "exposed_to": [],
            "documentation": C.BASE_URL + "/webmcp.html",
            "try_it": C.BASE_URL + "/?webmcp_debug=1",
        },
        "security": {
            "origin_scope": "same-origin only; tools are never registered with exposedTo",
            "cross_origin_frames": "refused unless the embedder grants the `tools` permissions policy",
            "input_validation": "JSON Schema subset per tool, with type, range, enum, length and depth limits",
            "prototype_pollution": "keys __proto__, prototype and constructor are rejected",
            "concurrency": "one in-flight call per tool; excess calls receive a BUSY envelope",
            "rate_limit": "90 calls per minute per document, 30 per tool, 100 ms minimum gap",
            "timeouts": "8 s per tool (15 s for the three dataset-backed tools)",
            "output_budget": f"{BUDGET['output']} characters per result, truncated deterministically",
            "network": "same-origin GETs of files under data/ only, credentials omitted, redirects refused",
            "errors": "structured envelopes, never stack traces",
            "rendering": "textContent only; innerHTML and eval are never used",
            "untrusted_content": "tools whose results contain GitHub text set untrustedContentHint",
        },
        "budgets": BUDGET,
        "tool_pages": {
            "all": "registered on every page",
            "repos": "registered where repository rows are embedded (home, language pages)",
            "table": "registered where a repository table is rendered",
            "home": "the homepage",
            "language": "a language page such as languages/python.html",
            "languages": "the language index",
            "methodology": "methodology.html",
            "dataset": "dataset.html",
            "compare": "compare.html",
            "faq": "faq.html",
            "webmcp": "webmcp.html",
            "404": "the not-found page",
        },
        "tools": [
            {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["inputSchema"],
                "annotations": tool["annotations"],
                "pages": tool["pages"],
                "timeout_ms": tool["timeoutMs"] or 8000,
            }
            for tool in tools
        ],
        "data_files": data_files or [],
    }


def data_files_manifest(ctx) -> list:
    files = []
    for key, info in ctx["langs"].items():
        path = DATA / "JSONL" / f"{key}.jsonl"
        files.append({
            "language": key,
            "display": info["display"],
            "path": f"data/JSONL/{key}.jsonl",
            "url": jsonl_url(key),
            "local_url": f"data/JSONL/{quote(key, safe='')}.jsonl",
            "records": info["n"],
            "bytes": info["size_bytes"],
            "sha256": info["sha256"],
            "markdown_url": md_file_url(key),
            "page": f"{C.BASE_URL}/languages/{info['slug']}.html",
            "exists": path.exists(),
        })
    return files


# ---------------------------------------------------------------------------
# 6. The human-facing documentation page
# ---------------------------------------------------------------------------

def page_webmcp(ctx, tools, manifest) -> str:
    """Build webmcp.html from the extracted catalogue, so the documentation and
    the registered tools are always the same list."""
    import build_site as B  # imported late: build_site imports this module

    url = f"{C.BASE_URL}/webmcp.html"
    groups = [
        ("Discover the site", ["get_site_info", "get_page_context", "list_languages",
                               "get_language_stats", "get_download_links"]),
        ("Query the data", ["get_top_repositories", "search_repositories",
                            "get_repository", "compare_repositories"]),
        ("Act on the page", ["filter_repository_table", "open_page"]),
        ("Read the documentation", ["get_methodology", "get_dataset_schema",
                                    "get_comparison", "answer_question"]),
        ("Diagnostics", ["run_webmcp_self_test"]),
    ]
    by_name = {tool["name"]: tool for tool in tools}

    sections = []
    for title, names in groups:
        rows = []
        for name in names:
            tool = by_name.get(name)
            if not tool:
                continue
            params = []
            props = tool["inputSchema"].get("properties", {})
            required = set(tool["inputSchema"].get("required", []))
            for param, spec in props.items():
                ptype = spec.get("type", "string")
                bits = [f"<code>{B.esc(param)}</code> <span class='small muted'>{B.esc(ptype)}</span>"]
                if param in required:
                    bits.append("<span class='small'><b>required</b></span>")
                enum = spec.get("enum")
                if isinstance(enum, list) and enum:
                    rendered = ", ".join("<code>%s</code>" % B.esc(v) for v in enum)
                    bits.append("<span class='small muted'>one of " + rendered + "</span>")
                default = spec.get("default")
                if default is not None:
                    bits.append("<span class='small muted'>default <code>%s</code></span>"
                                % B.esc(default))
                bits.append("<div class='small'>%s</div>" % B.esc(spec.get("description", "")))
                params.append("<li>" + " ".join(bits) + "</li>")
            annotations = tool["annotations"]
            flags = []
            if annotations.get("readOnlyHint"):
                flags.append("read-only")
            if annotations.get("untrustedContentHint"):
                flags.append("untrusted content")
            if annotations.get("consequentialHint"):
                flags.append("consequential")
            if annotations.get("debugging"):
                flags.append("debugging only")
            rows.append(
                f"<h3 id='tool-{B.esc(tool['name'])}'><code>{B.esc(tool['name'])}</code></h3>"
                f"<p>{B.esc(tool['description'])}</p>"
                f"<p class='small muted'>{B.esc(', '.join(flags) or 'no annotations')} &middot; "
                f"available on: {B.esc(', '.join(tool['pages']))}</p>"
                + (f"<ul class='params'>{''.join(params)}</ul>" if params else
                   "<p class='small muted'>No arguments.</p>")
            )
        sections.append(f"<h2 id='{B.esc(slugify(title))}'>{B.esc(title)}</h2>\n"
                        + "\n".join(rows))

    catalogue = "\n".join(sections)
    tool_count = len(tools)
    read_only = sum(1 for t in tools if t["annotations"].get("readOnlyHint"))
    untrusted = sum(1 for t in tools if t["annotations"].get("untrustedContentHint"))
    files_rows = "\n".join(
        f"<tr><td>{B.esc(item['display'])}</td>"
        f"<td><code>data/JSONL/{B.esc(item['language'])}.jsonl</code></td>"
        f"<td class='num'>{B.fmt(item['records'])}</td>"
        f"<td class='num'>{round(item['bytes'] / 1024, 1)} KB</td>"
        f"<td><code class='small'>{B.esc(item['sha256'][:16])}&hellip;</code></td></tr>"
        for item in manifest["data_files"]
    )

    body = f"""
<h1>WebMCP: AI agent tools for this site</h1>
<p class="lead">Top100 is an ordinary static website &mdash; and a WebMCP
<em>client-side MCP server</em> for the same content. An AI agent running in the
browser can discover {tool_count} tools here and call them directly instead of
scraping the tables, with the results the page itself would have produced.</p>

<ul class="facts">
<li><b>{tool_count}</b> WebMCP tools</li>
<li><b>{read_only}</b> read-only</li>
<li><b>{untrusted}</b> return GitHub text</li>
<li><b>{B.fmt(ctx['records'])}</b> repositories reachable</li>
<li><b>Same-origin</b> only, no cookies</li>
</ul>

<h2 id="try-it">Try the tools in this tab</h2>
<p>The fastest way to see WebMCP working is the debug panel on this site: it
lists every registered tool with its JSON Schema and lets you call it by hand,
through exactly the same validation, rate limiting and output budget an agent's
call goes through.</p>
<ul>
<li><a href="index.html?webmcp_debug=1">Open the homepage with the debug panel</a></li>
<li><a href="languages/python.html?webmcp_debug=1">Open a language page with the debug panel</a></li>
</ul>
<p>To drive the tools with a real agent, enable WebMCP in your browser:</p>
<ul>
<li><b>Chrome:</b> <code>chrome://flags/#enable-webmcp-testing</code> &rarr; Enabled,
then relaunch. Some builds instead run the
<a href="https://developer.chrome.com/originate/origintrials">origin trial</a>; the site
works with either.</li>
<li><b>Agent extensions:</b> the
<a href="https://chromewebstore.google.com/detail/model-context-tool-inspec/gbpdfapgefenggkahomfgkhfehlcenpd">Model
Context Tool Inspector</a> lists the tools and calls them with a prompt.</li>
<li><b>CLI agents:</b> <a href="https://agent-browser.dev/webmcp">agent-browser</a>
announces WebMCP tools automatically and can invoke them with
<code>agent-browser webmcp invoke</code>.</li>
<li><b>No browser support?</b> This site ships its own polyfill, so the tools
register anyway &mdash; see <a href="#polyfill">the polyfill section</a> below.</li>
</ul>

<h2 id="security">Security model</h2>
<p>WebMCP tools are code the page runs on the agent's behalf, so the interesting
questions are what a tool can reach, what it can change, and what a hostile
string could do once it is inside a model's context. The answers here are
deliberately boring.</p>
<div class="tablewrap"><table>
<caption>What this site does about each WebMCP risk, and where the code lives.</caption>
<thead><tr><th>Risk</th><th>Mitigation on this site</th></tr></thead>
<tbody>
<tr><td>Cross-origin reach</td><td>Tools are registered without <code>exposedTo</code>, so only
this origin can see or call them. Registration is skipped entirely inside a cross-origin
iframe unless the embedder granted <code>allow="tools"</code>.</td></tr>
<tr><td>Malformed or hostile arguments</td><td>Every call is validated against the tool's JSON
Schema before it runs: types, ranges, enum membership, 200-character string caps, array
length caps, four levels of nesting. Unknown arguments are ignored and reported back.</td></tr>
<tr><td>Prototype pollution</td><td><code>__proto__</code>, <code>prototype</code> and
<code>constructor</code> are rejected anywhere in an argument tree, and validated values are
copied into a fresh object.</td></tr>
<tr><td>Runaway agents</td><td>90 calls per minute per document, 30 per tool, a 100 ms
minimum gap, one in-flight call per tool, and an 8-second timeout (15 s for the three
tools that read a dataset file) wired to <code>AbortSignal</code>.</td></tr>
<tr><td>Context flooding</td><td>Results are capped at {BUDGET['output']} characters. Array
payloads are shrunk until the envelope fits and the result says exactly how many items were
dropped.</td></tr>
<tr><td>Prompt injection from repository text</td><td>Descriptions, topics and names come
from GitHub, so any tool that returns them declares
<code>untrustedContentHint: true</code> and every result carries
<code>"trust": "untrusted"</code> with a note. Control characters are stripped and every
free-text field is length-capped. Nothing on this site asks an agent to run a command,
reveal a secret or trust a suggestion.</td></tr>
<tr><td>Data exfiltration</td><td>The only network calls are same-origin GETs of files under
<code>data/</code>, with credentials omitted, redirects refused and a 4 MB ceiling. No
cookies, no analytics, no third-party requests, no <code>sendBeacon</code>.</td></tr>
<tr><td>Injection into the page</td><td>Tool results and tool names are rendered with
<code>textContent</code>; <code>innerHTML</code> and <code>eval</code> are never used
anywhere in the WebMCP code, and the build fails a test if they appear.</td></tr>
<tr><td>Silent automation</td><td>Tools act on the visible page and report what they did:
a live region announces every call, and the tools that change the page
(<code>filter_repository_table</code>, <code>open_page</code>) are the only two that are not
read-only. Both are annotated accordingly.</td></tr>
</tbody>
</table></div>

<h2 id="tools">Every tool</h2>
<p>Annotations follow the WebMCP <code>annotations</code> object:
<code>readOnlyHint</code> means the tool does not change anything,
<code>untrustedContentHint</code> means its result contains third-party text, and
<code>consequentialHint</code> &mdash; never set here, because nothing on this site books,
buys or deletes anything &mdash; would ask for user confirmation.</p>
{catalogue}

<h2 id="polyfill">How the runtime works</h2>
<p><code>assets/webmcp-core.js</code> does three things, in this order:</p>
<ol>
<li><b>Use what the browser has.</b> If <code>document.modelContext</code> exists (or the
older <code>navigator.modelContext</code> from the origin-trial builds), the tools are
registered there, unchanged.</li>
<li><b>Otherwise install a polyfill.</b> A dependency-free implementation of the same
surface &mdash; <code>registerTool</code>, <code>getTools</code>, <code>executeTool</code>,
<code>provideContext</code>, the <code>toolchange</code>, <code>toolactivated</code> and
<code>toolcancel</code> events, and unregistration through an
<code>AbortSignal</code> &mdash; is installed on <code>document.modelContext</code>. It never
replaces a real implementation, and it refuses to install on an insecure origin or in a
cross-origin frame without permission.</li>
<li><b>Wrap every tool in the same guard.</b> The validation, rate limiting, timeouts,
output budget and envelope formatting live inside each tool's <code>execute()</code>, so an
agent that calls the native <code>executeTool</code> gets exactly the same guarantees as one
that calls the polyfill.</li>
</ol>
<p>Two URL parameters exist for testing, and neither is read by anything else:
<code>?webmcp_debug=1</code> opens the debug panel, and
<code>?webmcp_polyfill=1</code> forces the polyfill even where the browser has native
support.</p>
<p>Tools are registered per page. A language page registers the tools that make sense for
its 100 rows; the FAQ page registers the documentation tools; nothing registers a tool it
cannot answer. The manifest of what is available where is published as
<a href="{C.BASE_URL}/data/webmcp-manifest.json">data/webmcp-manifest.json</a>.</p>

<h2 id="tool-manifest">For agents that never open the page</h2>
<p>WebMCP's own discoverability limit is that a client has to visit a page to know
what it offers. Two static artifacts cover the gap:</p>
<ul>
<li><a href="{C.BASE_URL}/data/webmcp-manifest.json"><code>data/webmcp-manifest.json</code></a>
&mdash; every tool with its full JSON Schema and annotations, the runtime facts, the
security model, and SHA-256 checksums for all {ctx['languages']} JSONL files.</li>
<li><a href="{C.BASE_URL}/llms.txt"><code>llms.txt</code></a> and
<a href="{C.BASE_URL}/llms-full.txt"><code>llms-full.txt</code></a> &mdash; the same site
described for agents that read text instead of calling tools.</li>
</ul>
<div class="tablewrap"><table>
<caption>Every data file with its checksum, for download verification.</caption>
<thead><tr><th>Language</th><th>File</th><th class="num">Records</th>
<th class="num">Size</th><th>SHA-256</th></tr></thead>
<tbody>
{files_rows}
</tbody>
</table></div>

<h2 id="limitations">Limitations, stated plainly</h2>
<ul>
<li>WebMCP is an early standard. The API shape is still moving; this site supports both
<code>document.modelContext</code> and the earlier <code>navigator.modelContext</code>, and
degrades to its own polyfill when neither exists.</li>
<li>A page must be open for its tools to exist. Nothing here works headless unless the
HTML is actually loaded in a browser.</li>
<li>Tool results are for one page's worth of context. Deep analysis across all 3,000
records belongs in the JSONL files, not in a tool result.</li>
<li><code>readOnlyHint</code> and friends are declarations, not enforcement. They are
accurate here, but a client should treat every page's claims as untrusted &mdash; as
OpenAI's and agent-browser's own documentation says.</li>
<li>Tools read the dataset snapshot embedded in the page or committed to the repository.
Between refreshes, they are as stale as the timestamp at the top of every page.</li>
</ul>

<h2 id="faq">Questions about the tools</h2>
<h3>Do I need a browser extension?</h3>
<p>No. Any browser with WebMCP support exposes these tools to whatever agent is running
there; the extension is only a convenient way to test.</p>
<h3>Does this change how the site works for people?</h3>
<p>No. Every page is complete HTML before any script runs, the WebMCP code adds a small
collapsible panel and nothing else, and with JavaScript off the site is byte-for-byte the
site it was.</p>
<h3>Is anything tracked?</h3>
<p>No cookies, no analytics, no third-party requests. The only network traffic the tools
generate is this site fetching its own data files.</p>
"""
    jsonld = [
        {"@context": "https://schema.org", "@graph": [
            B.jsonld_webpage(ctx, name="WebMCP: AI agent tools for Top100",
                             description="Every WebMCP tool this GitHub ranking site exposes to browser AI agents, with the security model behind them.",
                             page_url=url, page_type="TechArticle"),
            B.jsonld_breadcrumb([
                ("Top100", f"{C.BASE_URL}/"),
                ("WebMCP", url),
            ], url),
        ]},
    ]
    return B.html_page(
        ctx=ctx, prefix="", title="WebMCP: the AI agent tools on this site — Top100",
        description=(
            f"Top100 exposes {tool_count} WebMCP tools so browser AI agents can query the 3,000-record "
            "GitHub star ranking directly: schemas, annotations, security model, polyfill "
            "details and a debug panel."
        ),
        canonical=url, body=body, jsonld=jsonld,
        updated_line=f"Data refreshed {ctx['datetime_long']}",
        active="webmcp.html",
        webmcp=page_data(ctx, page_type="webmcp", page_path="webmcp.html"),
    )
