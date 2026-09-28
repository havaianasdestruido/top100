# Top100

**The 100 most-starred GitHub repositories for 30 programming languages, rebuilt every
hour from the GitHub Search API and published as raw JSONL you can download without an
API key.**

🌐 **Website:** <https://havaianasdestruido.github.io/top100/> · 📦 **Data:**
[`data/JSONL/`](data/JSONL) · 📖 **Methodology:**
[how the lists are built](https://havaianasdestruido.github.io/top100/methodology.html)

<a href="https://www.star-history.com/?repos=havaianasdestruido%2Ftop100&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=havaianasdestruido/top100&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=havaianasdestruido/top100&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=havaianasdestruido/top100&type=date&legend=top-left" />
 </picture>
</a>

## What you get

| Artifact | What it is |
| --- | --- |
| [`data/JSONL/<language>.jsonl`](data/JSONL) | One line per repository — the **full, untouched** object GitHub's Search API returns: owner, licence, topics, every count, every timestamp. 30 files × 100 records = 3,000 repositories. |
| [`data/TOP_<LANGUAGE>_100.md`](data) | A readable table per language: rank, name, stars, forks, open issues, licence, last push, description. |
| [The website](https://havaianasdestruido.github.io/top100/) | One indexable page per language (`Top 100 Rust Repositories by Stars`), a language index, statistics, a methodology page, a dataset field reference, a comparison against GitHub Trending and other ranking sites, and an FAQ. |
| [`feed.xml`](https://havaianasdestruido.github.io/top100/feed.xml) | RSS of data updates — one item per language, refreshed hourly. |

No scraping, no API key, no rate limit for readers: the JSONL files are static and
cacheable, and the whole dataset is ~17 MB.

## The current leaders

Refreshed hourly; these numbers are generated from the live dataset on every build.

<!-- LEADERS:START -->
| # | Repository | Language | Stars |
| --- | --- | --- | --- |
| 1 | [public-apis/public-apis](https://github.com/public-apis/public-apis) | Python | 484,055 |
| 2 | [freeCodeCamp/freeCodeCamp](https://github.com/freeCodeCamp/freeCodeCamp) | TypeScript | 456,457 |
| 3 | [EbookFoundation/free-programming-books](https://github.com/EbookFoundation/free-programming-books) | Python | 398,068 |
| 4 | [openclaw/openclaw](https://github.com/openclaw/openclaw) | TypeScript | 390,720 |
| 5 | [donnemartin/system-design-primer](https://github.com/donnemartin/system-design-primer) | Python | 372,344 |
| 6 | [nilbuild/developer-roadmap](https://github.com/nilbuild/developer-roadmap) | TypeScript | 368,422 |
| 7 | [vinta/awesome-python](https://github.com/vinta/awesome-python) | Python | 323,798 |
| 8 | [obra/superpowers](https://github.com/obra/superpowers) | Shell | 292,451 |
| 9 | [practical-tutorials/project-based-learning](https://github.com/practical-tutorials/project-based-learning) | Python | 285,095 |
| 10 | [mattpocock/skills](https://github.com/mattpocock/skills) | Shell | 271,223 |

Refreshed 28 September 2026, 18:00 UTC — these ten are the most-starred repositories across every language Top100 tracks.
<!-- LEADERS:END -->

See the [statistics table](https://havaianasdestruido.github.io/top100/#statistics) for
all 30 languages.

## How it works

One GitHub Search API request per language — that is the whole trick:

```
GET https://api.github.com/search/repositories
    ?q=language:Python&sort=stars&order=desc&per_page=100&page=1
```

GitHub returns at most 100 results per page, so `per_page=100` makes a "top 100" list
possible in a single call. No per-repository follow-up requests are made, so a full
refresh of all 30 languages costs **30 Search API requests**.

A scheduled GitHub Actions workflow runs that every hour, writes the JSONL and Markdown
files, rebuilds the website and commits everything back to this repository. The
[methodology page](https://havaianasdestruido.github.io/top100/methodology.html)
documents the query, the rate-limit back-off, the fields the Search API omits and the
known limitations.

## Run it yourself

```bash
# fetch the default 30 languages (needs a token: GH_TOKEN=...)
python scripts/fetch_top_repos.py

# or pick your own
LANGUAGES=Rust,Zig,Elixir python scripts/fetch_top_repos.py

# NB: fetching a language is free-form, but publishing it on the site is a config
# step - the builder reads LANGUAGES in scripts/site_content.py, so add a line there
# for any new language.

# rebuild the website from whatever is in data/
python scripts/build_site.py
```

From GitHub: **Actions → Top Repos by Language → Run workflow**, and pass a
comma-separated list of languages (blank = the default 30).

To fork and self-host, you only need the default `GITHUB_TOKEN` and
`permissions: contents: write` so the bot can commit the results. The Pages deployment
listens for the data workflow's completion, because commits made with the automatic
token do not re-trigger workflows.

## Languages

TypeScript, Python, JavaScript, Java, C#, C++, PHP, Shell, C, Go, Rust, Ruby, Kotlin,
Swift, Dart, HTML, CSS, SQL, Scala, Lua, Groovy, Objective-C, Perl, Haskell, Assembly,
R, Julia, Elixir, PowerShell, Nix.

## Notes

- The search-result item omits a handful of fields only the single-repo endpoint returns
  (`subscribers_count`, `network_count`, fork `parent`/`source`). Set
  `ENRICH_WITH_REPO_DETAILS = True` in `scripts/fetch_top_repos.py` if you need them —
  at ~100× the API usage.
- `language:` matches GitHub's *detected primary language*, so each repository appears
  in exactly one list.
- The data is GitHub API output; every listed project keeps its own licence. The
  script and site are MIT licensed.

## License

[MIT](LICENSE)
