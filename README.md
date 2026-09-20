# Top100

## Star History

<a href="https://www.star-history.com/?repos=havaianasdestruido%2Ftop100&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=havaianasdestruido/top100&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=havaianasdestruido/top100&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=havaianasdestruido/top100&type=date&legend=top-left" />
 </picture>
</a>


TOP 100 GitHub repositories for each major programming language, listed by stars.

## Demo

Check [LISTS.md](LISTS.md).

## About
What it writes:
- `data/JSONL/<language>.jsonl` — one line per repo, each line is the **full, untouched** repo object GitHub's search API returns (owner, license, topics, stats, timestamps, everything).
- `data/TOP_<LANGUAGE>_100.md` — a readable table: rank, name, stars, forks, open issues, license, last push, description.

Notes:
- Languages are set via the `languages` workflow input (comma-separated), defaulting to `TypeScript,Python,JavaScript,Java,C#,C++,PHP,Shell,C,Go,Rust,Ruby,Kotlin,Swift,Dart,HTML,CSS,SQL,Scala,Lua,Groovy,Objective-C,Perl,Haskell,Assembly,R,Julia,Elixir,PowerShell,Nix`.
- The search-result item omits a handful of fields only the single-repo endpoint returns (e.g. `subscribers_count`, `network_count`).
- The workflow needs `permissions: contents: write` (included) so it can commit the results back.
