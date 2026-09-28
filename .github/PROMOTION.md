# Getting Top100 cited outside its own repository

The AI-visibility scan of this project came back with one unmistakable finding: **zero
third-party sites reference it**. Every discoverable mention traces back to the owner's
own repositories. AI assistants answer "what are the top GitHub repositories by stars?"
with the projects that *other people* write about — EvanLi/Github-Ranking,
gitstar-ranking.com, Top1000Repos — not with a repository nobody has linked to.

The code half of that problem is now fixed: the site publishes 30 indexable per-language
pages, a methodology page, a dataset field reference, a comparison page, an FAQ with
direct answers, JSON-LD, a sitemap and an `llms.txt`. This file is the other half —
the outside-the-repo work, with everything pre-written so it takes minutes rather than
an evening.

**Golden rule: be useful, not promotional.** Every post below leads with the artifact
(a free 17 MB JSONL dataset) and says what it is for. Post it where you would
genuinely answer the same question, disclose that it is your project, and stop. One
good thread per community beats five identical ones.

---

## 0. Settings only the owner can change

The automation bot does not have permission to modify repository settings. Do these by
hand (two minutes):

- [ ] **Topics** on <https://github.com/havaianasdestruido/top100> → About ⚙️:
      `github`, `github-api`, `github-actions`, `jsonl`, `dataset`, `open-data`,
      `ranking`, `top-repositories`, `data-collection`, `developer-tools`, `python`
- [ ] **Description** → `Top 100 GitHub repositories by stars for 30 programming
      languages, with a free JSONL dataset of raw GitHub Search API objects, refreshed
      hourly.`
- [ ] **Website** → `https://havaianasdestruido.github.io/top100/`
- [ ] **Discussions** → enable, and pin a "what should I add next?" thread
- [ ] **Social preview image** (Settings → Social preview) — a 1280×640 image reading
      "Top 100 GitHub repositories by stars · 30 languages · free JSONL" — this is what
      shows up when the repo is shared anywhere

---

## 1. Hugging Face dataset mirror (highest leverage, ~30 minutes)

AI systems read Hugging Face heavily, and a dataset card is a permanent, citable,
machine-readable page that links back to the site. Do this first.

```bash
# 1. create the dataset repo at https://huggingface.co/new-dataset
#    name: havaianasdestruido/github-top100-repositories  (public)
# 2. clone it and copy the data in
git clone https://huggingface.co/datasets/havaianasdestruido/github-top100-repositories
cd github-top100-repositories
mkdir -p data
for f in ../../top100/data/JSONL/*.jsonl; do cp "$f" data/; done
```

Paste the card below as `README.md`, then:

```bash
git add . && git commit -m "Add top 100 GitHub repositories per language (3000 records)"
git push
```

<details>
<summary>Dataset card to paste</summary>

```markdown
---
license: other
license_name: github-api-terms
task_categories:
  - text-classification
language:
  - en
tags:
  - github
  - repositories
  - stars
  - ranking
  - jsonl
  - open-data
size_categories:
  - n<1K
pretty_name: Top 100 GitHub repositories by language
---

# Top 100 GitHub repositories by language

3,000 GitHub repository records: the 100 most-starred repositories for each of 30
programming languages, rebuilt every hour from the GitHub Search API.

Every line of every file is the **complete, unmodified JSON object** GitHub's Search
API returned — owner, licence, topics, all counts, all timestamps, all feature flags.
Nothing is dropped, renamed or reshaped, so the files load straight into DuckDB,
pandas, jq or BigQuery.

## Files

One file per language, 100 newline-delimited JSON records each (~17 MB total):
`python.jsonl`, `typescript.jsonl`, `javascript.jsonl`, `java.jsonl`, `c.jsonl`,
`cpp.jsonl`, `csharp.jsonl`, `go.jsonl`, `rust.jsonl`, `ruby.jsonl`, `php.jsonl`,
`swift.jsonl`, `kotlin.jsonl`, `dart.jsonl`, `scala.jsonl`, `shell.jsonl`, `html.jsonl`,
`css.jsonl`, `sql.jsonl`, `lua.jsonl`, `groovy.jsonl`, `objective-c.jsonl`,
`perl.jsonl`, `haskell.jsonl`, `assembly.jsonl`, `r.jsonl`, `julia.jsonl`,
`elixir.jsonl`, `powershell.jsonl`, `nix.jsonl`.

## Use

```python
from datasets import load_dataset
ds = load_dataset("json", data_files="python.jsonl")
print(ds["train"][0]["full_name"], ds["train"][0]["stargazers_count"])
```

```bash
duckdb -c "SELECT full_name, stargazers_count, license.spdx_id
           FROM read_json_auto('python.jsonl')
           ORDER BY stargazers_count DESC LIMIT 10;"
```

## Provenance and refresh

Collected with one GitHub Search API request per language
(`?q=language:<name>&sort=stars&order=desc&per_page=100`) by a scheduled GitHub
Actions workflow that commits the results hourly. The data is GitHub API output:
each listed project keeps its own licence. Check the `license` field before reusing
anyone's code.

Full tables, statistics, methodology and field reference:
**https://havaianasdestruido.github.io/top100/**

Source: https://github.com/havaianasdestruido/top100
```

</details>

---

## 2. Show HN (~15 minutes)

Best posted Tuesday–Thursday, 08:00–10:00 ET. Title matters more than anything else.

> **Title:** Show HN: Top 100 GitHub repositories by stars for 30 languages, as JSONL

> **Body:**
>
> I got tired of re-running the same GitHub search to see what is actually popular in a
> language, so I automated it: a scheduled workflow asks the GitHub Search API for the
> top 100 repositories by stars in each of 30 languages, once an hour, and commits the
> raw response.
>
> The useful part is the format. Each JSONL line is the complete, untouched object the
> Search API returned — owner, licence, topics, every count, every timestamp — so you
> can analyse it without scraping anything. One request per language, so a full refresh
> costs 30 API calls.
>
> It also builds a static site: one page per language, a methodology page explaining
> the query and the limitations, and a comparison against GitHub Trending and the other
> ranking sites.
>
> Happy to answer questions about the pipeline or the Search API's quirks.

---

## 3. Reddit (~30 minutes total, one post per subreddit)

Pick the two or three where the dataset genuinely answers a recurring question.
Answer existing threads first if you can find them — that is worth more than a new post.

**r/datasets** (title: *Free dataset: top 100 GitHub repositories per language, 3,000
records, raw Search API JSON*)

> I publish the 100 most-starred GitHub repositories for each of 30 programming
> languages as JSONL — 3,000 records total, each one the complete, unmodified JSON
> object from GitHub's Search API (owner, licence, topics, counts, timestamps).
>
> Refreshed hourly by a GitHub Actions workflow; no API key or rate limit to download.
> Field reference and per-language tables:
> https://havaianasdestruido.github.io/top100/
>
> My project, posting it here because r/datasets seemed like the right place to ask:
> what would make this more useful for you — more languages, historical snapshots, or
> a consolidated single file?

**r/github** (title: *I built a per-language top 100 GitHub repos dataset that refreshes
hourly*)

> Every hour a workflow queries the Search API for the 100 most-starred repositories in
> 30 languages and commits the raw JSON back. The site turns that into one page per
> language plus stats like "stars needed to reach 100th place" (7 for SQL, 57,558 for
> Python — the spread is wild).
>
> https://havaianasdestruido.github.io/top100/
>
> Limitations are documented on the methodology page: no history, single primary
> language per repo, forks not filtered. What would you want fixed first?

**r/dataengineering** (title: *A small, boring, actually-working example of scheduled
data collection with GitHub Actions*)

> Not a framework — one Python script, one Search API request per language, and an
> automatic commit back to the repo every hour. The interesting bits are the rate-limit
> back-off and the fact that commits made with GITHUB_TOKEN don't re-trigger workflows,
> which is why the Pages deploy listens for the data workflow's completion instead of
> for pushes.
>
> Write-up: https://havaianasdestruido.github.io/top100/methodology.html

---

## 4. Product Hunt (~20 minutes)

Launch on a Tuesday–Thursday. Tagline and description below.

> **Tagline:** The top 100 GitHub repos per language, refreshed hourly

> **Description:**
> Top100 answers one question — what are the most-starred GitHub repositories in this
> language? — for 30 languages, every hour.
>
> • One indexable page per language: Top 100 Rust repositories, Top 100 Python
>   repositories, and so on
> • Raw JSONL download: 3,000 records, each the complete GitHub Search API object
> • Star-threshold statistics: 7 stars to enter the SQL top 100, 57,558 for Python
> • Methodology, field reference and an honest comparison against GitHub Trending,
>   gitstar-ranking.com and EvanLi/Github-Ranking
>
> Static site, no JavaScript, no tracking. Free and open source.

---

## 5. Awesome lists and indexes (~1 hour, highest citation value per minute)

Submit the project where the tools it competes with are already listed. These are the
indexes AI models read when they answer "what are the top GitHub repositories by stars?".

| Target | Where |
| --- | --- |
| `sindresorhus/awesome` | PR to the relevant section (data / GitHub tooling) |
| `EbookFoundation/free-programming-books` | only if you add a real entry |
| `awesome-dataset/awesome-datasets` | GitHub / open data section |
| `github.com/topics/github-api` | automatic once topics are set (see §0) |
| LibHunt | https://libhunt.com — submit under Go/Python/Ruby topics |
| AlternativeTo | list as an alternative to "GitHub Trending" and "gitstar-ranking" |
| Openbase | https://openbase.com — submit as a GitHub data tool |
| StackShare | https://stackshare.io — submit the stack used |
| OSS Insight collections | if it accepts community collections |

Submission snippet that works everywhere:

> **Top100** — top 100 GitHub repositories by stars for 30 programming languages,
> published as raw JSONL (3,000 records, one Search API object per line) and as
> per-language web pages, refreshed hourly by a GitHub Actions workflow.
> https://havaianasdestruido.github.io/top100/ · https://github.com/havaianasdestruido/top100

---

## 6. Answers, not announcements

The single highest-value thing you can do is answer the questions that already exist.
Search these and reply where the current answers are incomplete:

- Stack Overflow: "github most starred repositories api", "github search api sort stars"
- Quora: "what are the most starred repositories on GitHub"
- Reddit search: `site:reddit.com top 100 github repositories stars`
- GitHub Discussions in data-tooling repos: "where do I get github repo metadata"

Answer first, link second, and only when the dataset actually solves the asker's
problem.

---

## 7. What to measure

Check these every two weeks; they move slowly and that is normal.

- [ ] Does `havaianasdestruido/top100` appear in the AI answers to the eight buying
      questions? (re-run the scan)
- [ ] GitHub stars / forks on the repo (currently 1 / 0)
- [ ] Referring domains in GitHub traffic insights (Settings → Traffic)
- [ ] Google Search Console coverage once the sitemap is picked up
- [ ] Are the hourly Pages deployments actually running? (Actions → Deploy Jekyll)

The realistic timeline is 60–90 days for the site half of this to show up in assistant
answers, because that is roughly how long the citation graph takes to notice.
