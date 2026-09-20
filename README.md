# Top100

TOP 100 GitHub repositories for each major programming language, listed by stars.

## Demo

Check [LISTS.MD](LISTS.MD).

## About
What it writes:
- `data/JSONL/<language>.jsonl` — one line per repo, each line is the **full, untouched** repo object GitHub's search API returns (owner, license, topics, stats, timestamps, everything).
- `data/TOP_<LANGUAGE>_100.md` — a readable table: rank, name, stars, forks, open issues, license, last push, description.

Notes:
- Languages are set via the `languages` workflow input (comma-separated), defaulting to `TypeScript,Python,JavaScript,Java,C#,C++,PHP,Shell,C,Go,Rust,Ruby,Kotlin,Swift,Dart,HTML,CSS,SQL,Scala,Lua,Groovy,Objective-C,Perl,Haskell,Assembly,R,Julia,Elixir,PowerShell,Nix`.
- The search-result item omits a handful of fields only the single-repo endpoint returns (e.g. `subscribers_count`, `network_count`).
- The workflow needs `permissions: contents: write` (included) so it can commit the results back.
