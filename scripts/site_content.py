#!/usr/bin/env python3
"""
All human-written content for the Top100 static site, kept separate from the
HTML assembly logic in build_site.py.

Functions that need live numbers (top-10 tables, statistics) receive a `ctx`
dictionary built by build_site.py.
"""

# ---------------------------------------------------------------------------
# Site configuration
# ---------------------------------------------------------------------------

SITE_TITLE = "Top100 — Top 100 GitHub repositories by stars"
SITE_NAME = "Top100"
BASE_URL = "https://havaianasdestruido.github.io/top100"
REPO_FULL_NAME = "havaianasdestruido/top100"
REPO_URL = "https://github.com/havaianasdestruido/top100"
BLOB_URL = REPO_URL + "/blob/main"
TREE_URL = REPO_URL + "/tree/main"
RAW_URL = "https://raw.githubusercontent.com/havaianasdestruido/top100/main"
LANGUAGE_COUNT = 30
RECORDS_PER_LANGUAGE = 100

# ---------------------------------------------------------------------------
# Languages: key (as used in the JSONL filename), display name, URL slug,
# and a short hand-written note about what that language's top 100 looks like.
# Order here is the order used on the language index page.
# ---------------------------------------------------------------------------

LANGUAGES = [
    ("typescript", "TypeScript", "typescript",
     "TypeScript's top 100 is the modern web toolchain: type-safe frameworks, "
     "build tools, editors-as-apps and full-stack kits. It is also where the "
     "single largest educational repositories on GitHub live."),
    ("python", "Python", "python",
     "Python's ranking is the most crowded on GitHub. Learning resources, "
     "automation agents, ML frameworks and CLI utilities dominate, and the "
     "bar to reach 100th place is the highest of any language."),
    ("javascript", "JavaScript", "javascript",
     "JavaScript has the deepest bench of any language: even the 100th "
     "repository on this list is a household name, and frameworks, UI kits "
     "and 'awesome' lists fill most of the table."),
    ("java", "Java", "java",
     "Java's top 100 is enterprise infrastructure, build tooling, "
     "Android-adjacent libraries and a large amount of algorithm and "
     "interview-preparation material."),
    ("c#", "C#", "csharp",
     "C#'s ranking is .NET tooling, desktop utilities, media servers and game "
     "mods. It is also the most permissively licensed list in the dataset — "
     "MIT alone covers more than 40 of the 100 repositories."),
    ("c++", "C++", "cpp",
     "C++ is where the big runtimes live: machine-learning frameworks, LLM "
     "inference engines, game engines, browsers and quant libraries."),
    ("php", "PHP", "php",
     "PHP's list mixes frameworks, self-hosting platforms and security "
     "wordlists. The most-starred PHP repository is not a framework at all "
     "but SecLists, a collection of security testing payloads."),
    ("shell", "Shell", "shell",
     "Shell's ranking is unusually top-heavy: two agent-skill repositories "
     "sit close to 300,000 stars, well above oh-my-zsh and the other "
     "long-standing favourites."),
    ("c", "C", "c",
     "C's top 100 is systems software: the Linux kernel, screen mirroring "
     "tools, Windows utilities and the embedded and database projects that "
     "everything else is built on."),
    ("go", "Go", "go",
     "Go's top 100 is cloud-native infrastructure: awesome-go, local LLM "
     "runtimes, the Go toolchain itself, and a long tail of CLIs, "
     "controllers and operators."),
    ("rust", "Rust", "rust",
     "Rust's top 100 is CLI reimplementations, proxy and networking tools, "
     "and systems projects. The star counts climb fast, so the entry bar is "
     "one of the highest outside the three biggest languages."),
    ("ruby", "Ruby", "ruby",
     "Ruby's ranking still opens with Rails, followed by personal-finance "
     "tooling, Jekyll and the gems that powered a generation of startups."),
    ("kotlin", "Kotlin", "kotlin",
     "Kotlin's top repositories are Android clients, rooting and system "
     "tools, and Jetpack-adjacent libraries."),
    ("swift", "Swift", "swift",
     "Swift's ranking is Apple-platform development: macOS utilities, iOS UI "
     "kits, the Swift toolchain and a large volume of interview-preparation "
     "repositories."),
    ("dart", "Dart", "dart",
     "Dart's ranking is effectively the Flutter ecosystem. The Flutter "
     "repository has roughly twice as many stars as the runner-up, and the "
     "rest of the list is cross-platform app frameworks and tools."),
    ("html", "HTML", "html",
     "HTML-tagged repositories are mostly documentation and course material: "
     "self-taught computer-science curricula, prompt collections, free-tier "
     "lists and design systems."),
    ("css", "CSS", "css",
     "CSS's top 100 is animation libraries, icon and font collections, CSS "
     "frameworks and the small utilities that shaped modern styling."),
    ("sql", "SQL", "sql",
     "SQL is the smallest list here — GitHub only reports a few thousand "
     "repositories whose primary language is SQL — and the entry bar is "
     "correspondingly low."),
    ("scala", "Scala", "scala",
     "Scala's list is big-data infrastructure: a major social network's "
     "open-sourced ranking algorithm, Apache Spark, and the Lichess game "
     "server."),
    ("lua", "Lua", "lua",
     "Lua's top repositories are Neovim starter configurations, API "
     "gateways, game modding and scripting tools."),
    ("groovy", "Groovy", "groovy",
     "Groovy's ranking is dominated by Gradle and the Jenkins plugin "
     "ecosystem; only about a hundred thousand GitHub repositories use it as "
     "their primary language."),
    ("objective-c", "Objective-C", "objective-c",
     "Objective-C's ranking is a snapshot of the pre-Swift iOS era: "
     "networking and image-loading libraries, plus macOS extensions."),
    ("perl", "Perl", "perl",
     "Perl's most-starred repositories are the utilities that outlived the "
     "language's peak: line counters, flame graphs and diff formatters."),
    ("haskell", "Haskell", "haskell",
     "Haskell's list mixes compilers, document converters and type-level "
     "experiments with genuinely practical tools such as shellcheck and "
     "PostgREST."),
    ("assembly", "Assembly", "assembly",
     "Assembly's list is a museum as much as a ranking: the Apollo 11 "
     "guidance computer source, Microsoft's early MS-DOS releases and "
     "malware source archives."),
    ("r", "R", "r",
     "R is a comparatively small community, and its top 100 is dominated by "
     "statistics visualisation, teaching material and a handful of "
     "much-shared opinion pieces."),
    ("julia", "Julia", "julia",
     "Julia's ranking is extremely front-loaded: the language repository "
     "itself has roughly ten times the stars of the runner-up."),
    ("elixir", "Elixir", "elixir",
     "Elixir's list is small but healthy — Phoenix-adjacent tooling, "
     "analytics, orchestration and job queues."),
    ("powershell", "PowerShell", "powershell",
     "PowerShell's top 100 is Windows debloating and utility scripts, led by "
     "Chris Titus Tech's winutil."),
    ("nix", "Nix", "nix",
     "Nix is the smallest community in this dataset, and its ranking is "
     "effectively nixpkgs, home-manager and a scattering of CTF tooling."),
]

LANG_NOTES = {key: (display, slug, note) for key, display, slug, note in LANGUAGES}

# ---------------------------------------------------------------------------
# Stylesheet (small, no JavaScript, dark-mode aware)
# ---------------------------------------------------------------------------

CSS = """/* Top100 static site - intentionally tiny, no JS, no web fonts */
:root{
  --bg:#ffffff; --fg:#1b1f24; --muted:#5b6472; --line:#e2e7ee; --card:#f6f8fa;
  --accent:#0b62d0; --accent-fg:#ffffff; --chip:#eaf1fb; --star:#9a6700;
}
@media (prefers-color-scheme:dark){
  :root{
    --bg:#0d1117; --fg:#e6edf3; --muted:#9aa7b6; --line:#232a33; --card:#161b22;
    --accent:#4c8ef7; --accent-fg:#08111f; --chip:#182433; --star:#d29922;
  }
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
}
a{color:var(--accent);text-decoration:none}
a:hover,a:focus{text-decoration:underline}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px}
.skip{position:absolute;left:-9999px}
.skip:focus{left:8px;top:8px;background:var(--card);padding:8px 12px;z-index:5}
header.site{border-bottom:1px solid var(--line);background:var(--card)}
header.site .wrap{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:center;padding-top:12px;padding-bottom:12px}
.brand{font-weight:700;font-size:1.15rem;color:var(--fg)}
.brand span{color:var(--accent)}
nav.site{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:.95rem;margin-left:auto}
nav.site a{color:var(--muted)}
nav.site a:hover{color:var(--accent)}
main.wrap{padding-top:24px;padding-bottom:48px}
h1{font-size:2rem;line-height:1.25;margin:0 0 12px}
h2{font-size:1.4rem;line-height:1.3;margin:40px 0 12px}
h3{font-size:1.1rem;margin:28px 0 8px}
p{margin:0 0 14px}
ul,ol{margin:0 0 14px;padding-left:24px}
li{margin:0 0 6px}
.lead{font-size:1.1rem;color:var(--fg)}
.muted{color:var(--muted)}
.small{font-size:.9rem}
.updated{
  display:inline-block;background:var(--chip);border:1px solid var(--line);
  border-radius:999px;padding:4px 14px;font-size:.85rem;color:var(--muted);margin:0 0 20px
}
.facts{display:flex;flex-wrap:wrap;gap:10px;list-style:none;padding:0;margin:0 0 24px}
.facts li{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px;font-size:.9rem}
.facts b{display:block;font-size:1.25rem;line-height:1.2}
.tablewrap{overflow-x:auto;margin:0 0 20px;border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:.92rem;background:var(--bg)}
caption{caption-side:top;text-align:left;padding:12px 14px;color:var(--muted);font-size:.88rem}
th,td{padding:8px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--card);font-size:.82rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.rank{color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap}
.stars{color:var(--star);font-weight:600;white-space:nowrap}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px;list-style:none;padding:0;margin:0 0 20px}
.grid li{border:1px solid var(--line);border-radius:8px;padding:12px 14px;background:var(--card)}
.grid a{font-weight:600}
.grid .sub{display:block;font-size:.85rem;color:var(--muted);margin-top:2px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin:0 0 20px;padding:0;list-style:none}
.cards li{border:1px solid var(--line);border-radius:10px;padding:16px}
pre{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px;overflow-x:auto;font-size:.85rem;line-height:1.5}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.9em}
p code,li code,td code{background:var(--chip);border-radius:4px;padding:1px 5px}
pre code{background:none;padding:0}
.note{border-left:3px solid var(--accent);background:var(--card);padding:12px 16px;border-radius:0 8px 8px 0;margin:0 0 20px}
footer.site{border-top:1px solid var(--line);background:var(--card);padding:24px 0;color:var(--muted);font-size:.9rem}
footer.site .wrap{display:flex;flex-wrap:wrap;gap:8px 20px}
footer.site a{color:var(--muted)}
details{border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin:0 0 10px;background:var(--card)}
summary{cursor:pointer;font-weight:600}
details[open] summary{margin-bottom:8px}
@media (max-width:640px){
  h1{font-size:1.6rem}
  nav.site{margin-left:0;width:100%}
}
"""

# ---------------------------------------------------------------------------
# Homepage / FAQ copy
# ---------------------------------------------------------------------------


def faq_entries(ctx):
    """The eight buying questions, each answered in 40-70 words of quotable
    prose. Answers may contain [text](url) links."""
    top5 = ctx["top_overall"][:5]
    if len(top5) >= 5:
        top_answer = (
            f"As of {ctx['date_long']}, the most-starred repositories on GitHub are "
            f"{top5[0]['full_name']} with {ctx['fmt'](top5[0]['stargazers_count'])} stars, "
            f"{top5[1]['full_name']} with {ctx['fmt'](top5[1]['stargazers_count'])}, "
            f"{top5[2]['full_name']} with {ctx['fmt'](top5[2]['stargazers_count'])}, "
            f"{top5[3]['full_name']} with {ctx['fmt'](top5[3]['stargazers_count'])} and "
            f"{top5[4]['full_name']} with {ctx['fmt'](top5[4]['stargazers_count'])}. "
            "Top100 rebuilds this ranking every hour from the GitHub Search API, so the "
            "table above is never more than an hour old."
        )
    else:
        top_answer = (
            f"As of {ctx['date_long']}, the most-starred repositories on GitHub are "
            "listed in the table above. Top100 rebuilds this ranking every hour from "
            "the GitHub Search API, so the table is never more than an hour old."
        )
    return [
        (
            "What are the top GitHub repositories by stars right now?",
            top_answer,
        ),
        (
            "Where can I find a top 100 GitHub repositories list?",
            "Top100 publishes a top 100 GitHub repositories list for 30 programming "
            "languages, ranked by stars. Each language has its own page — Top 100 "
            "Python repositories, Top 100 Rust repositories, Top 100 Go repositories "
            "and so on — with rank, stars, forks, open issues, licence and last push "
            "for every entry. The lists are rebuilt hourly and the raw data is "
            "downloadable as JSONL.",
        ),
        (
            "How can I see the top repositories for each programming language?",
            "Start from the [language index](languages/index.html): it links to a "
            "ranked table of the 100 most-starred repositories for each of the 30 "
            "languages covered, from Python and JavaScript to Nix and SQL. Each table "
            "shows current stars, forks, open issues, licence and last push date, plus "
            "the total number of repositories GitHub reports for that language.",
        ),
        (
            "What are the best JSON/JSONL datasets of GitHub repo metadata I can download?",
            "Top100 ships 30 JSONL files — one per language, 100 repositories each, "
            f"{ctx['fmt'](ctx['records'])} records in total — where every line is the "
            "complete repository object returned by GitHub's Search API. For other "
            "shapes of data: GH Archive covers event streams, BigQuery's public "
            "github_repos dataset gives you SQL access, and GHTorrent publishes "
            "periodic full dumps.",
        ),
        (
            "Is there a free tool to export GitHub repository metadata as JSON?",
            "Yes. Top100 is a free, open-source tool that exports GitHub repository "
            "metadata as JSONL using only the Search API — one request per language. "
            "Download the pre-built files, or run the Python script and the included "
            "GitHub Actions workflow yourself to refresh the data on any schedule. No "
            "credentials beyond GitHub's own automatic token are required.",
        ),
        (
            "How do I set up a GitHub Actions scheduled workflow to collect data automatically?",
            "Create a workflow file under `.github/workflows/` with an "
            "`on.schedule` cron entry, check out the repository, run your "
            "fetch script with the automatic `GITHUB_TOKEN`, then commit and "
            "push the results — the job needs `permissions: contents: write`. "
            "Top100 does exactly this every hour; the [methodology "
            "page](methodology.html) has the complete workflow and script.",
        ),
        (
            "What are the best GitHub Actions workflows for automated data collection projects?",
            "For scheduled scraping, Simon Willison's git-scraping pattern and GitHub's "
            "Flat Data action are the standard starting points. Top100's own workflow is "
            "a minimal alternative: one Python script, one API call per language, and an "
            "automatic commit of fresh JSONL and Markdown tables back to the repository.",
        ),
        (
            "What is the average number of GitHub stars and how do repos rank by stars?",
            f"GitHub ranks repositories by `stargazers_count`. Across the "
            f"{ctx['fmt'](ctx['records'])} repositories in Top100's lists the median is "
            f"{ctx['fmt'](ctx['median_stars'])} stars and the mean is "
            f"{ctx['fmt'](ctx['mean_stars'])}, but the distribution is heavily skewed: "
            f"the bar to enter a top 100 ranges from {ctx['fmt'](ctx['min_bar'])} stars "
            f"for {ctx['min_bar_lang']} to {ctx['fmt'](ctx['max_bar'])} for "
            f"{ctx['max_bar_lang']}. See the "
            "[statistics table](index.html#statistics) for the per-language "
            "thresholds.",
        ),
    ]


def extra_faq_entries(ctx):
    """Additional questions that only appear on the FAQ page."""
    return [
        (
            "Is the Top100 dataset free to use?",
            "Yes. Every file is published in a public GitHub repository and can be "
            "downloaded, forked or mirrored without an account, an API key or a rate "
            "limit. The repository metadata itself comes from GitHub's public API, and "
            "each project keeps its own licence — check the `license` field "
            "before reusing anyone's code.",
        ),
        (
            "How often is the Top100 data refreshed?",
            "Every hour. A scheduled GitHub Actions workflow runs at minute zero of "
            f"every hour, re-queries the Search API for all {LANGUAGE_COUNT} languages "
            "and commits the results back to the repository. Every page on this site "
            "shows the timestamp of the refresh that produced it, and the "
            "[update feed](feed.xml) lists the newest leader of each language.",
        ),
        (
            "Can I add another language to the list?",
            "Yes, but it takes one line of configuration. Trigger the workflow from the "
            "Actions tab with a comma-separated list of languages, or run "
            "`LANGUAGES=Rust,Zig python scripts/fetch_top_repos.py` locally — each "
            "language costs exactly one Search API request. To publish the new language "
            "on the site, also add it to `LANGUAGES` in `scripts/site_content.py`: the "
            "site builder reads that list rather than scanning `data/`.",
        ),
        (
            "Do the lists include forks and archived repositories?",
            f"Forks, no; archived repositories, yes. GitHub's repository search excludes "
            f"forks unless the query adds `fork:true` or `fork:only`, which is why "
            f"{ctx['forks_in_data']} of the {ctx['fmt'](ctx['records'])} listed repositories "
            f"are forks. Archived repositories are included, and "
            f"{ctx['archived_in_data']} of them are archived and read-only.",
        ),
        (
            "Why is my repository missing from a top 100 list?",
            "Three common reasons. GitHub assigns each repository a single detected "
            "primary language, so a polyglot project may be listed under a different "
            "language. The repository may also simply sit below the 100th-place star "
            "count shown on that language's page. Finally, the Search API occasionally "
            "returns `incomplete_results` for very broad queries.",
        ),
        (
            "What is the difference between Top100 and GitHub Trending?",
            "GitHub Trending shows what is gaining stars today, this week or this month "
            "and only lists a couple of dozen repositories, with no export. Top100 "
            "ranks by total stars, covers 100 repositories per language across 30 "
            "languages, and publishes the raw JSON. Use Trending for discovery and "
            "Top100 when you need a complete, machine-readable snapshot.",
        ),
        (
            "Does Top100 have an API?",
            "Not a hosted one — the point of the project is that you do not need one. "
            "The JSONL files are static and cacheable, so you can download them "
            "directly, or query them in place with DuckDB, jq or pandas without "
            "touching GitHub's rate limits.",
        ),
        (
            "How should I cite or attribute the dataset?",
            "Link to this site or to the repository, and credit GitHub as the source of "
            "the metadata. A reasonable citation is “Top 100 GitHub repositories by "
            f"language, havaianasdestruido/top100, data refreshed {ctx['date_long']}”. "
            "The per-page refresh timestamps are the version identifier, since the data "
            "changes hourly.",
        ),
    ]


# ---------------------------------------------------------------------------
# Methodology page
# ---------------------------------------------------------------------------

METHODOLOGY = {
    "title": "Methodology — how Top100 collects the top 100 GitHub repositories by language",
    "description": (
        "The exact GitHub Search API query, sort order, refresh cadence and known "
        "limitations behind every top 100 list on this site."
    ),
    "h1": "Methodology: how the top 100 GitHub repositories are collected",
    "sections": [
        (
            "The query",
            """
<p>Every list on this site is the result of a single GitHub Search API request per
language:</p>
<pre><code>GET https://api.github.com/search/repositories
    ?q=language:Python
    &amp;sort=stars
    &amp;order=desc
    &amp;per_page=100
    &amp;page=1</code></pre>
<p>GitHub returns at most 100 results per page for this endpoint, so
<code>per_page=100</code> is exactly what makes a "top 100" list possible in one
call. <code>sort=stars&amp;order=desc</code> ranks by
<code>stargazers_count</code>; no other ordering is applied anywhere on the site.</p>
""",
        ),
        (
            "One API request per language",
            """
<p>There are no per-repository follow-up calls. A naive implementation would call
<code>GET /repos/{owner}/{repo}</code> for every row to "complete" the data, which
would multiply API usage by roughly 100×. The search-result item already contains
almost everything GitHub knows about a repository — owner, licence, topics, every
count, all timestamps — so the script keeps it as-is and stays at
<strong>one request per language per run</strong>.</p>
<p>For the default list of 30 languages that is 30 requests per refresh, comfortably
inside the authenticated Search API limit of 30 requests per minute.</p>
""",
        ),
        (
            "The data is never reshaped",
            """
<p>Each line of <code>data/JSONL/&lt;language&gt;.jsonl</code> is the full JSON
object GitHub returned, serialised back to JSON with no fields dropped, renamed,
rounded or reordered. If GitHub adds a field tomorrow, it appears in the next
refresh automatically. The <a href="dataset.html">field reference</a> documents
what is in there and what is not.</p>
""",
        ),
        (
            "Refresh cadence and automation",
            """
<p>A scheduled GitHub Actions workflow runs at minute zero of every hour
(<code>cron: "0 0/1 * * *"</code>), re-fetches all 30 languages, rebuilds the
Markdown tables, rebuilds this website and commits everything back to the
repository. The job needs <code>permissions: contents: write</code> so the bot can
commit, and the resulting commit does not re-trigger the Pages deployment, so the
deploy job is wired to the data workflow's completion instead.</p>
<p>You can also trigger a run by hand from the Actions tab and pass any
comma-separated list of languages.</p>
""",
        ),
        (
            "Rate limits and back-off",
            """
<p>Authenticated requests get 30 Search API requests per minute; unauthenticated
requests get 10. The script reads <code>X-RateLimit-Remaining</code> after each
language and, when it is nearly exhausted, sleeps until
<code>X-RateLimit-Reset</code>. HTTP 403 and 429 responses are retried with
exponential back-off using <code>Retry-After</code> when GitHub sends it.</p>
""",
        ),
        (
            "What the Search API does not return",
            """
<p>A handful of fields exist only on the single-repository endpoint:
<code>subscribers_count</code>, <code>network_count</code>, the
<code>parent</code>/<code>source</code> objects for forks,
<code>code_of_conduct</code> and <code>security_and_analysis</code>. The script can
optionally merge them by calling
<code>GET /repos/{owner}/{repo}</code> for every result — set
<code>ENRICH_WITH_REPO_DETAILS = True</code> in
<code>scripts/fetch_top_repos.py</code> — but that turns one request per language
into about 101, so it is off by default.</p>
""",
        ),
        (
            "Known limitations",
            """
<ul>
<li><strong>Language is a single label.</strong> GitHub assigns each repository one
detected primary language. A project written half in Python and half in C appears
in only one list.</li>
<li><strong>Forks are excluded by default.</strong> GitHub's repository search leaves
forks out unless the query adds <code>fork:true</code> or <code>fork:only</code>, so a
fork never displaces the repository it was copied from, however many stars it has.
Archived repositories, by contrast, <em>are</em> included: they are read-only but
public, and a few of them rank highly.</li>
<li><strong><code>total_count</code> is approximate for very broad queries.</strong>
GitHub reports a number that can be much larger than the 1,000 results it will
actually page through, and occasionally answers with
<code>incomplete_results: true</code>. The site reports the number GitHub returned
rather than pretending it is exact.</li>
<li><strong>No history.</strong> This is a snapshot refreshed hourly, not a time
series. For star trends over time use Star History or OSS Insight; for event-level
history use GH Archive or BigQuery.</li>
<li><strong>Ranking by stars only.</strong> Stars are a popularity signal, not a
quality signal, and they accumulate forever — which is why a 2014 tutorial can
outrank a better 2026 tool.</li>
</ul>
""",
        ),
        (
            "Run it yourself",
            """
<pre><code># locally (needs a token with public_repo / no scope for public data)
GH_TOKEN=ghp_xxx LANGUAGES=Python,Rust python scripts/fetch_top_repos.py

# or let GitHub do it: Actions → "Top Repos by Language" → Run workflow
# and pass the languages you want as a comma-separated input.</code></pre>
<p>The workflow is self-contained: <code>actions/checkout</code>, Python 3.12, the
script, and a commit step. Fork the repository and it will refresh your own copy
every hour.</p>
""",
        ),
    ],
    "closing": """
<p>Every number on this site is reproducible: the workflow, the script and the
resulting data all live in the same
<a href="https://github.com/havaianasdestruido/top100">repository</a>, and the
<a href="https://github.com/havaianasdestruido/top100/commits/main">commit
history</a> is the changelog.</p>
""",
}

# ---------------------------------------------------------------------------
# Dataset page
# ---------------------------------------------------------------------------

DATASET_INTRO = """
<p>Each JSONL file holds 100 records — one per repository — and each record is the
complete, untouched JSON object returned by GitHub's Search API. The files are
UTF-8 encoded newline-delimited JSON: one object per line, no wrapping array, no
trailing commas, no reshaping. That makes them streamable with
<code>jq</code>, loadable by <code>pandas.read_json(lines=True)</code>, and
queryable in place by DuckDB and BigQuery.</p>
"""

DATASET_LOADING = """
<h3>Download and query</h3>
<pre><code># one language
curl -sSL -o python.jsonl \\
  https://raw.githubusercontent.com/havaianasdestruido/top100/main/data/JSONL/python.jsonl

# the current leaders, straight from the file
jq -r '.full_name + "  " + (.stargazers_count|tostring)' python.jsonl | head

# SQL over the raw file, no import step
duckdb -c "SELECT full_name, stargazers_count, license.spdx_id
          FROM read_json_auto('python.jsonl')
          ORDER BY stargazers_count DESC LIMIT 10;"

# Python
import json
repos = [json.loads(line) for line in open("python.jsonl", encoding="utf-8")]
print(repos[0]["full_name"], repos[0]["stargazers_count"])</code></pre>
<p>Because the files are static, they are friendly to caches, mirrors and Hugging
Face dataset mirrors: there is nothing to authenticate and no rate limit to
respect.</p>
"""

# Field reference: (field, type, description)
DATASET_FIELDS = [
    ("Identity", None, None),
    ("id", "integer", "GitHub's numeric repository ID. Stable across renames and transfers."),
    ("node_id", "string", "GraphQL global node ID for the repository."),
    ("name", "string", "Repository name without the owner, e.g. `top100`."),
    ("full_name", "string", "`owner/repo`. The canonical identifier used in every URL and API path on this site."),
    ("private", "boolean", "Always `false` here: the Search API only returns public repositories for an unauthenticated caller."),
    ("visibility", "string", "Always `public`."),
    ("owner", "object", "The owning account: `login`, `id`, `type` (`User` or `Organization`), avatar URLs and API URLs."),
    ("URLs", None, None),
    ("html_url", "string", "Human URL, e.g. `https://github.com/owner/repo`."),
    ("url", "string", "API URL, e.g. `https://api.github.com/repos/owner/repo`."),
    ("*_url", "string", "API endpoints for sub-resources: `forks_url`, `issues_url`, `pulls_url`, `labels_url`, `releases_url`, `deployments_url`, `languages_url`, `stargazers_url`, `contributors_url`, `commits_url`, `contents_url`, `compare_url`, `archive_url`, `downloads_url`, `branches_url`, `tags_url`, `blobs_url`, `git_refs_url`, `trees_url`, `statuses_url`, `keys_url`, `collaborators_url`, `teams_url`, `hooks_url`, `issue_events_url`, `events_url`, `assignees_url`, `comments_url`, `issue_comment_url`, `commits_url`, `git_commits_url`, `merges_url`, `milestones_url`, `subscription_url`, `subscribers_url`. Templates contain placeholders such as `{/branch}` or `{/sha}`."),
    ("git_url", "string", "`git://` URL."),
    ("ssh_url", "string", "SSH clone URL."),
    ("clone_url", "string", "HTTPS clone URL."),
    ("svn_url", "string", "Subversion URL."),
    ("homepage", "string|null", "Project website declared in the repository settings. Empty for most repositories."),
    ("mirror_url", "string|null", "Set only for mirrored repositories."),
    ("Timestamps (ISO 8601, UTC)", None, None),
    ("created_at", "string", "When the repository was created. Useful for age-normalising star counts."),
    ("updated_at", "string", "When any repository metadata last changed (description, topics, stars, …)."),
    ("pushed_at", "string", "When code was last pushed. For archived or abandoned repositories this can be years older than `updated_at`."),
    ("Counts", None, None),
    ("stargazers_count", "integer", "Number of stars. The ranking key for every list on this site."),
    ("watchers_count", "integer", "Number of users who starred the repository. GitHub returns the same value as `stargazers_count` here; the true subscriber count is `subscribers_count`, which this endpoint does not return."),
    ("forks_count", "integer", "Number of forks."),
    ("open_issues_count", "integer", "Open issues plus open pull requests."),
    ("size", "integer", "Repository size in kilobytes, as GitHub accounts it. Lags behind aggressive history rewrites."),
    ("forks / open_issues / watchers", "integer", "Duplicates of the `*_count` fields, kept because the raw object contains both spellings."),
    ("Flags", None, None),
    ("has_issues", "boolean", "Whether the issues tab is enabled."),
    ("has_projects", "boolean", "Whether the projects tab is enabled."),
    ("has_downloads", "boolean", "Whether the downloads tab is enabled."),
    ("has_wiki", "boolean", "Whether the wiki is enabled."),
    ("has_pages", "boolean", "Whether GitHub Pages is enabled for the repository."),
    ("has_discussions", "boolean", "Whether discussions are enabled."),
    ("archived", "boolean", "Whether the repository is read-only and archived."),
    ("disabled", "boolean", "Whether GitHub has disabled the repository."),
    ("allow_forking", "boolean", "Whether forking is permitted."),
    ("is_template", "boolean", "Whether the repository can be used as a template."),
    ("web_commit_signoff_required", "boolean", "Whether commits must be signed off."),
    ("has_pull_requests", "boolean", "Whether pull requests are enabled."),
    ("pull_request_creation_policy", "string", "Who may open pull requests (`all` or `collaborators_only`)."),
    ("Classification", None, None),
    ("license", "object|null", "`{key, name, spdx_id, url, node_id}`. `spdx_id` is the machine-readable identifier (`MIT`, `Apache-2.0`, `GPL-3.0`, …); `NOASSERTION` means GitHub could not map the licence to an SPDX ID."),
    ("language", "string|null", "GitHub's detected primary language. Every list on this site filters on this field."),
    ("topics", "array<string>", "Repository topics — the closest thing GitHub has to keywords, and a useful join key for your own analysis."),
    ("default_branch", "string", "Usually `main` or `master`."),
    ("Search API artifacts", None, None),
    ("score", "number", "The Search API's internal relevance score for this result. With `sort=stars` it is mostly monotonic, but it is not a meaningful quantity — ignore it."),
    ("permissions", "object", "The calling token's permissions on this repository (`admin`, `push`, `pull`). An artifact of the authenticated request, not repository metadata."),
]

DATASET_MISSING = """
<h3>Fields that are not in these files</h3>
<p>The single-repository endpoint returns a few extra fields the Search API omits:
<code>subscribers_count</code>, <code>network_count</code>, the
<code>parent</code> and <code>source</code> objects for forks,
<code>code_of_conduct</code>, <code>security_and_analysis</code> and
<code>temp_clone_token</code>. Set <code>ENRICH_WITH_REPO_DETAILS = True</code> in
<code>scripts/fetch_top_repos.py</code> if you need them — at the cost of roughly
100 extra API requests per language.</p>
"""

# ---------------------------------------------------------------------------
# Comparison page
# ---------------------------------------------------------------------------

COMPARISON = {
    "title": "Top100 vs GitHub Trending, gitstar-ranking, EvanLi/Github-Ranking and other sources",
    "description": (
        "An honest comparison of Top100 against GitHub Trending, gitstar-ranking.com, "
        "EvanLi/Github-Ranking, OSS Insight, Star History, GH Archive and BigQuery."
    ),
    "h1": "How Top100 compares to other GitHub ranking sources",
    "intro": """
<p>There are two families of GitHub ranking tools: <em>human-facing leaderboards</em>
that answer "what is popular?" and <em>data platforms</em> that answer "what
happened?". Top100 deliberately sits in a narrow gap between them: a
leaderboard-shaped view of a data-platform-shaped export. This page says exactly
where it wins and where it does not, because the honest answer is usually "use
both".</p>
""",
    "rows": [
        (
            "<strong>Top100</strong> (this site)",
            "Top 100 repositories by stars for 30 languages, plus raw JSONL of every record.",
            "HTML tables + JSONL + Markdown",
            "Hourly",
            "Yes — 30 languages",
            "Yes — direct JSONL download",
        ),
        (
            "<a href=\"https://github.com/EvanLi/Github-Ranking\">EvanLi/Github-Ranking</a>",
            "Top 100 by stars and top 100 by forks per language, published as Markdown tables in the repo README.",
            "Markdown only",
            "Daily",
            "Yes",
            "No — tables only",
        ),
        (
            "<a href=\"https://gitstar-ranking.com/\">gitstar-ranking.com</a>",
            "Unofficial star ranking of 10,000 users, organizations and repositories.",
            "HTML tables",
            "Regularly",
            "No — global list",
            "No",
        ),
        (
            "<a href=\"https://top1000repos.com/\">Top1000Repos.com</a>",
            "Top 1,000 repositories sortable by stars, pull requests and issues.",
            "HTML table",
            "Daily",
            "No — global list",
            "No",
        ),
        (
            "<a href=\"https://github.com/trending\">GitHub Trending</a>",
            "What is gaining stars today, this week or this month; a couple of dozen repositories.",
            "HTML only, no API",
            "Daily",
            "Yes — filterable",
            "No",
        ),
        (
            "<a href=\"https://github.com/search?q=stars%3A%3E0&amp;s=stars&amp;type=repositories\">GitHub Search</a>",
            "Any query you can express, including stars, language, topics and dates.",
            "HTML + REST API",
            "Live",
            "Yes",
            "Yes — via the API",
        ),
        (
            "<a href=\"https://ossinsight.io/\">OSS Insight</a>",
            "Deep analytics: star velocity, contributor trends, collections and SQL playground over GitHub Archive.",
            "HTML + SQL",
            "Hourly",
            "Partly",
            "Query results only",
        ),
        (
            "<a href=\"https://star-history.com/\">Star History</a>",
            "Star curves over time for any set of repositories.",
            "Charts + images",
            "On demand",
            "No",
            "No",
        ),
        (
            "<a href=\"https://www.gharchive.org/\">GH Archive</a>",
            "Every public GitHub event since 2011, hour by hour, as gzipped JSON.",
            "JSON (events)",
            "Hourly",
            "No — event stream",
            "Yes — bulk download",
        ),
        (
            "<a href=\"https://cloud.google.com/bigquery/docs/github-public-dataset\">BigQuery public GitHub datasets</a>",
            "Petabyte-scale GitHub data queryable in SQL, including repository snapshots.",
            "SQL tables",
            "Hourly / daily",
            "Partly",
            "Query results only",
        ),
    ],
    "use_top100": [
        "You want the top 100 for a specific language, not the global top 10.",
        "You need the <em>raw</em> repository object — topics, licence, timestamps, counts — not a screenshot of a table.",
        "You want a file you can <code>curl</code>, cache, mirror or load into DuckDB without an API key or a rate limit.",
        "You are building something that must stay current, and hourly is often enough.",
        "You want a worked example of scheduled GitHub Actions data collection you can fork.",
    ],
    "use_other": [
        "You need star <em>trends</em> over months or years → Star History or OSS Insight.",
        "You want to know what is hot <em>right now</em> → GitHub Trending.",
        "You need event-level history (commits, issues, PRs) → GH Archive or BigQuery.",
        "You need every repository, not the top 100 → GitHub Search, GH Archive or GHTorrent.",
        "You want rankings of users and organizations, not repositories → gitstar-ranking.com.",
    ],
    "closing": """
<p>Checked against those sources in September 2026. If a comparison row has gone
stale, the <a href="https://github.com/havaianasdestruido/top100/issues">issue
tracker</a> is the fastest way to correct it.</p>
""",
}
