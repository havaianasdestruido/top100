/*!
 * Top100 — WebMCP tools (v1.0.0)
 *
 * Every tool this site exposes to an AI agent. Loaded after webmcp-core.js,
 * which owns the model context, the validation pipeline, the rate limits, the
 * output budget and the human-visible status line.
 *
 * Tool definitions are strict JSON literals on purpose: scripts/webmcp_catalog.py
 * parses this file to build the machine-readable tool manifest and the
 * documentation page, and scripts/test_webmcp.py fails the build if a tool
 * breaks the naming, annotation or character-budget rules below.
 *
 * Conventions used by every tool here:
 *   - names are lower_snake_case, unique, <= 30 characters
 *   - descriptions are <= 500 characters and say what the tool returns
 *   - `pages` lists where the tool is registered: "all", "repos", "table",
 *     "home", "language", "languages", "methodology", "dataset", "compare",
 *     "faq", "404"
 *   - execute() returns a plain object or throws a core SiteError; the core
 *     converts both into the same structured envelope.
 *   - nothing throws on bad input, nothing writes to the page except
 *     filter_repository_table and open_page, and nothing leaves this origin.
 */
(function () {
  "use strict";

  var Core = window.Top100WebMCP;
  if (!Core) return; // core failed to load: the site keeps working without us

  var H = Core.helpers;
  var LIMITS = Core.limits;

  // Small local aliases so the definitions below stay readable.
  var clean = H.clean;
  var fmt = H.fmt;
  var validate = H.validate;
  var languageByKey = H.languageByKey;
  var pageRoutes = H.pageRoutes;
  var define = Core.defineTool;

  var READ_ONLY = { "readOnlyHint": true, "untrustedContentHint": false, "consequentialHint": false, "debugging": false };
  var READ_ONLY_UNTRUSTED = { "readOnlyHint": true, "untrustedContentHint": true, "consequentialHint": false, "debugging": false };
  var PAGE_ACTION = { "readOnlyHint": false, "untrustedContentHint": false, "consequentialHint": false, "debugging": false };
  var PAGE_ACTION_UNTRUSTED = { "readOnlyHint": false, "untrustedContentHint": true, "consequentialHint": false, "debugging": false };
  var DEBUG_ONLY = { "readOnlyHint": true, "untrustedContentHint": false, "consequentialHint": false, "debugging": true };

  /* ===================================================================== *
   * 1. Identity and freshness — what this site is, what page you are on.
   * ===================================================================== */

  define({
    name: "get_site_info",
    description: "Describe the Top100 site: what it publishes, how fresh the data is, " +
      "how many languages and repositories it ranks, where the raw JSONL lives, and " +
      "which pages exist. Call this first when you need to know what this site can " +
      "answer or how current its numbers are.",
    inputSchema: {
      "type": "object",
      "properties": {},
      "required": []
    },
    annotations: READ_ONLY,
    pages: ["all"],
    execute: function () {
      var site = Core.data.site || {};
      var langs = Core.data.languages || [];
      return {
        site: clean(site.name || "Top100", 40),
        summary: "The 100 most-starred GitHub repositories for " + langs.length +
          " programming languages, rebuilt hourly from the GitHub Search API and " +
          "published as raw JSONL.",
        homepage: clean(site.base_url || "", 120),
        source_repository: clean(site.repo_url || "", 120),
        license: "MIT (site and scripts); each listed repository keeps its own licence",
        attribution: "Repository metadata is GitHub's, retrieved through GitHub's public Search API",
        data: {
          as_of: clean(Core.data.asOf, 30),
          languages: langs.length,
          repositories: Number(site.records) || (langs.length * 100),
          jsonl_bytes: Number(site.jsonl_bytes) || 0,
          refresh: "hourly",
          unauthenticated: true,
          cookies: false,
          tracking: false
        },
        pages: Object.keys(pageRoutes()).map(function (key) {
          return { page: key, url: clean(site.base_url + "/" + pageRoutes()[key].replace(/^(\.\.\/)+/, ""), 140) };
        })
      };
    }
  });

  define({
    name: "get_page_context",
    description: "Return where the user is right now: page type, canonical URL, the " +
      "language this page covers (if any), how many repository rows are on the page, " +
      "and the timestamp of the data being shown. Use it to resolve deictic prompts " +
      "such as \"this list\" or \"the table here\".",
    inputSchema: {
      "type": "object",
      "properties": {},
      "required": []
    },
    annotations: READ_ONLY_UNTRUSTED,
    pages: ["all"],
    execute: function () {
      var page = Core.data.page || {};
      var lang = page.language ? languageByKey(page.language) : null;
      return {
        page_type: clean(page.type || "unknown", 40),
        url: clean(page.url || window.location.href.split("#")[0], 160),
        title: clean(document.title, 160),
        language: lang ? {
          key: lang.key,
          display: clean(lang.display, 40),
          page: H.languageUrl(lang.key)
        } : null,
        repositories_on_page: (Core.data.repos || []).length,
        sections: Array.prototype.slice.call(document.querySelectorAll("h2[id]"))
          .slice(0, 12).map(function (h) { return clean(h.id, 40); }),
        data_as_of: clean(Core.data.asOf, 30),
        tools_available: (Core.state || {}).registered || 0
      };
    }
  });

  /* ===================================================================== *
   * 2. The language index — every list the site publishes.
   * ===================================================================== */

  define({
    name: "list_languages",
    description: "List the languages Top100 ranks, with each one's most-starred " +
      "repository, the star count to reach 100th place, the median inside the top 100 " +
      "and how many repositories GitHub reports for it. Paged: five rows per call, " +
      "use offset to walk all 30. Every row's page URL is base_url + /languages/<slug>.html.",
    inputSchema: {
      "type": "object",
      "properties": {
        "sort": {
          "type": "string",
          "enum": ["rank", "leader_stars", "entry_bar", "name"],
          "description": "rank (site order), leader_stars, entry_bar or name.",
          "default": "rank"
        },
        "limit": {
          "type": "integer",
          "minimum": 1,
          "maximum": 30,
          "description": "Rows to return, 1-30. Default 5.",
          "default": 5
        },
        "offset": {
          "type": "integer",
          "minimum": 0,
          "maximum": 29,
          "description": "Row to start from, 0-based, for paging.",
          "default": 0
        }
      },
      "required": []
    },
    annotations: READ_ONLY_UNTRUSTED,
    pages: ["all"],
    execute: function (args) {
      var site = Core.data.site || {};
      var langs = (Core.data.languages || []).slice();
      var sort = args.sort || "rank";
      if (sort === "leader_stars") {
        langs.sort(function (a, b) { return (b.max_stars || 0) - (a.max_stars || 0); });
      } else if (sort === "entry_bar") {
        langs.sort(function (a, b) { return (b.min_stars || 0) - (a.min_stars || 0); });
      } else if (sort === "name") {
        langs.sort(function (a, b) { return String(a.display).localeCompare(String(b.display)); });
      }
      var keep = Math.max(1, Math.min(args.limit || 5, 30));
      var offset = Math.max(0, Math.min(args.offset || 0, Math.max(0, langs.length - 1)));
      var slice = langs.slice(offset, offset + keep);
      return {
        total_languages: langs.length,
        offset: offset,
        returned: slice.length,
        remaining: Math.max(0, langs.length - offset - slice.length),
        data_as_of: clean(Core.data.asOf, 30),
        languages: slice.map(function (lang) {
          return {
            key: clean(lang.key, 20),
            display: clean(lang.display, 40),
            slug: clean(lang.slug, 30),
            leader: clean(lang.leader, 80),
            leader_stars: Number(lang.max_stars) || 0,
            entry_stars: Number(lang.min_stars) || 0,
            median_stars: Number(lang.median_stars) || 0,
            repos_reported: Number(lang.total_count) || 0
          };
        })
      };
    }
  });

  define({
    name: "get_language_stats",
    description: "Statistics for one language's top 100: the leading repository and its " +
      "stars, the entry bar for 100th place, the median star count, the most common " +
      "licence and how many of the 100 use it, the JSONL download with its record count " +
      "and SHA-256 checksum, and a one-line description of the list. Accepts a language " +
      "key such as python, c++, c# or objective-c.",
    inputSchema: {
      "type": "object",
      "properties": {
        "language": {
          "type": "string",
          "description": "Language key, for example python, rust, c++, c#.",
          "maxLength": 30
        }
      },
      "required": ["language"]
    },
    annotations: READ_ONLY_UNTRUSTED,
    pages: ["all"],
    execute: function (args) {
      var lang = languageByKey(args.language);
      if (!lang) throw new H.SiteError("NOT_FOUND", "No tracked language matched that name.");
      var onThisPage = (Core.data.repos || []).length &&
        (Core.data.page || {}).language === lang.key;
      return {
        language: clean(lang.key, 20),
        display: clean(lang.display, 40),
        page: clean((Core.data.site || {}).base_url + "/languages/" + lang.slug + ".html", 140),
        summary: clean(lang.note, 240),
        repositories_github_reports: Number(lang.total_count) || 0,
        ranked: 100,
        leader: clean(lang.leader, 80),
        leader_stars: Number(lang.max_stars) || 0,
        stars_to_enter_top_100: Number(lang.min_stars) || 0,
        median_stars: Number(lang.median_stars) || 0,
        most_common_license: clean(lang.top_license || "NOASSERTION", 24),
        most_common_license_count: Number(lang.top_license_n) || 0,
        repositories_on_this_page: onThisPage ? (Core.data.repos || []).length : 0,
        top_repositories_tool: onThisPage ? "get_top_repositories (this page)" : "open the language page first",
        jsonl_url: clean(lang.jsonl, 200),
        jsonl_sha256: clean(lang.sha256, 64),
        markdown_url: clean(lang.markdown, 200),
        __notes: onThisPage ? [] : ["Use open_page with this language to get its rows."]
      };
    }
  });

  define({
    name: "get_download_links",
    description: "List every file this site publishes for machine use, with its URL: the " +
      "JSONL dataset (one file per language), the Markdown lists, feed.xml, sitemap.xml, " +
      "robots.txt, llms.txt, llms-full.txt, README.md, LISTS.md, the search index and " +
      "the WebMCP manifest that carries all 30 checksums. Pass language=<key> for one " +
      "file's size and SHA-256; pass family=dataset for the per-language URLs.",
    inputSchema: {
      "type": "object",
      "properties": {
        "language": {
          "type": "string",
          "description": "Language key for one dataset file, for example python.",
          "maxLength": 30
        },
        "family": {
          "type": "string",
          "description": "Which family of files to return.",
          "enum": ["all", "site", "dataset"],
          "default": "all"
        }
      },
      "required": []
    },
    annotations: READ_ONLY,
    pages: ["all"],
    execute: function (args) {
      var site = Core.data.site || {};
      var base = clean(site.base_url, 120) || "https://havaianasdestruido.github.io/top100";
      var langs = Core.data.languages || [];
      var family = args.family || "all";

      if (args.language) {
        var lang = languageByKey(args.language);
        if (!lang) throw new H.SiteError("NOT_FOUND", "No tracked language matched that name.");
        return {
          family: "dataset",
          language: clean(lang.key, 20),
          display: clean(lang.display, 40),
          jsonl_url: clean(lang.jsonl, 200),
          jsonl_bytes: Number(lang.size_bytes) || 0,
          jsonl_records: 100,
          jsonl_sha256: clean(lang.sha256, 64),
          markdown_url: clean(lang.markdown, 200),
          language_page: clean(base + "/languages/" + lang.slug + ".html", 160)
        };
      }

      var payload = {
        family: family,
        base_url: base,
        data_as_of: clean(site.data_as_of || site.fetched_at || Core.data.asOf, 30)
      };

      if (family !== "dataset") {
        // Paths are relative to base_url, so the origin appears exactly once
        // and an agent joins them as base_url + "/" + path.
        payload.site_files = [
          { file: "data/search-index.json", path: "data/search-index.json", note: "3,000 records, one per repository" },
          { file: "data/webmcp-manifest.json", path: "data/webmcp-manifest.json", note: "tools, files, every SHA-256" },
          { file: "data/webmcp-context.json", path: "data/webmcp-context.json", note: "methodology and fields as data" },
          { file: "feed.xml", path: "feed.xml", note: "RSS 2.0 ranking feed" },
          { file: "sitemap.xml", path: "sitemap.xml", note: "every published page" },
          { file: "llms.txt", path: "llms.txt", note: "summary for language models" },
          { file: "llms-full.txt", path: "llms-full.txt", note: "whole site as plain text" },
          { file: "README.md", path: "README.md", note: "source repository README" },
          { file: "LISTS.md", path: "LISTS.md", note: "Markdown list index" },
          { file: "robots.txt", path: "robots.txt", note: "crawl rules; all data is public" }
        ];
      }

      payload.dataset = {
        files: langs.length,
        records_per_file: 100,
        records_total: Number(site.records) || langs.length * 100,
        total_bytes: Number(site.jsonl_bytes) || 0,
        url_pattern: base + "/data/JSONL/<language-key>.jsonl",
        checksums: base + "/data/webmcp-manifest.json"
      };

      if (family === "dataset") {
        payload.dataset.languages = langs.map(function (lang) {
          return { key: clean(lang.key, 20), url: clean(lang.jsonl, 160) };
        });
        payload.dataset.__notes = ["language=<key> returns one file's SHA-256."];
      } else if (family !== "site") {
        payload.__notes = ["family=dataset returns all 30 URLs; language=<key> one checksum."];
      }

      return payload;
    }
  });

  /* ===================================================================== *
   * 3. Repository data — page rows and the full 3,000-record index.
   * ===================================================================== */

  define({
    name: "get_top_repositories",
    description: "Return a ranked slice of the repository table on the current page: " +
      "rank, name, stars, forks, licence, last push and a short description. On a " +
      "language page this is that language's top 100; on the homepage it is the overall " +
      "top 10. Five rows by default, up to 25 (larger requests are trimmed to the result " +
      "budget and say so). Use get_repository for the full record of one row.",
    inputSchema: {
      "type": "object",
      "properties": {
        "limit": {
          "type": "integer",
          "minimum": 1,
          "maximum": 25,
          "description": "Rows to return, 1-25.",
          "default": 5
        },
        "offset": {
          "type": "integer",
          "minimum": 0,
          "maximum": 99,
          "description": "Rank to start from, 0-based.",
          "default": 0
        },
        "sort": {
          "type": "string",
          "enum": ["stars", "stars_asc", "forks", "issues", "recent", "name"],
          "description": "stars (default), stars_asc, forks, issues, recent or name.",
          "default": "stars"
        },
        "license": {
          "type": "string",
          "description": "Keep only this SPDX licence id, for example MIT or Apache-2.0.",
          "maxLength": 30
        },
        "min_stars": {
          "type": "integer",
          "minimum": 0,
          "maximum": 1000000,
          "description": "Keep only repositories with at least this many stars."
        }
      },
      "required": []
    },
    annotations: READ_ONLY_UNTRUSTED,
    pages: ["repos"],
    execute: function (args) {
      var rows = (Core.data.repos || []).slice();
      if (args.license) {
        var want = String(args.license).toLowerCase();
        rows = rows.filter(function (r) {
          return String(r.license || "NOASSERTION").toLowerCase() === want;
        });
      }
      if (typeof args.min_stars === "number") {
        rows = rows.filter(function (r) { return (Number(r.stars) || 0) >= args.min_stars; });
      }
      var sorted = H.sortRecords(rows.map(function (r) {
        return {
          stars: Number(r.stars) || 0,
          forks: Number(r.forks) || 0,
          open_issues: Number(r.open_issues) || 0,
          pushed_at: r.pushed_at || "",
          full_name: r.full_name || "",
          row: r
        };
      }), args.sort || "stars");
      var offset = Math.max(0, args.offset || 0);
      var limit = Math.max(1, Math.min(args.limit || 5, 25));
      var slice = sorted.slice(offset, offset + limit);
      var page = Core.data.page || {};
      return {
        scope: page.language ? clean(page.language, 20) + " top 100 (this page)"
          : "overall top 10 (this page)",
        matches: sorted.length,
        offset: offset,
        returned: slice.length,
        github_url_pattern: "https://github.com/<full_name>",
        repositories: slice.map(function (item, index) {
          var r = item.row;
          return {
            rank: offset + index + 1,
            full_name: clean(r.full_name, 80),
            stars: Number(r.stars) || 0,
            forks: Number(r.forks) || 0,
            license: clean(r.license || "NOASSERTION", 24),
            pushed_at: clean(r.pushed_at, 12),
            description: clean(r.description, 64)
          };
        })
      };
    }
  });

  define({
    name: "search_repositories",
    description: "Search all 3,000 repositories in the dataset by keyword (matched " +
      "against name, description and topics) with optional filters for language, star " +
      "range, SPDX licence and topic. Returns ranked matches with stars, forks, licence " +
      "and page links. Sorting is deterministic: relevance, stars, forks, issues or " +
      "recency.",
    inputSchema: {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "Keywords, for example \"design system\" or \"llm agents\".",
          "maxLength": 120,
          "default": ""
        },
        "language": {
          "type": "string",
          "description": "Restrict to one language key, for example python or rust.",
          "maxLength": 30
        },
        "min_stars": {
          "type": "integer",
          "minimum": 0,
          "maximum": 1000000,
          "description": "Minimum stars."
        },
        "max_stars": {
          "type": "integer",
          "minimum": 0,
          "maximum": 1000000,
          "description": "Maximum stars."
        },
        "license": {
          "type": "string",
          "description": "Exact SPDX licence id, for example MIT.",
          "maxLength": 30
        },
        "topic": {
          "type": "string",
          "description": "Exact topic tag, for example cli or machine-learning.",
          "maxLength": 40
        },
        "sort": {
          "type": "string",
          "enum": ["relevance", "stars", "forks", "issues", "recent", "name"],
          "description": "relevance (default), stars, forks, issues, recent or name.",
          "default": "relevance"
        },
        "limit": {
          "type": "integer",
          "minimum": 1,
          "maximum": 20,
          "description": "Matches to return, 1-20.",
          "default": 5
        }
      },
      "required": []
    },
    annotations: READ_ONLY_UNTRUSTED,
    pages: ["repos", "home", "languages"],
    timeoutMs: 15000,
    execute: function (args) {
      var lang = args.language ? languageByKey(args.language) : null;
      if (args.language && !lang) {
        throw new H.SiteError("NOT_FOUND", "No tracked language matched \"" +
          clean(args.language, 30) + "\".");
      }
      return H.loadSearchIndex().then(function (index) {
        var records = index.repos.map(H.indexRecord).filter(Boolean);
        var matches = H.searchRecords(records, args.query, {
          language: lang ? lang.key : null,
          minStars: args.min_stars,
          maxStars: args.max_stars,
          license: args.license,
          topic: args.topic,
          sort: args.sort,
          langBoost: (Core.data.page || {}).language || null
        });
        var limit = Math.max(1, Math.min(args.limit || 5, 20));
        return {
          query: clean(args.query || "", 120),
          scanned: records.length,
          matches: matches.length,
          returned: Math.min(limit, matches.length),
          index_generated_at: clean(index.generated_at, 30),
          results: matches.slice(0, limit).map(function (r) {
            return {
              full_name: r.full_name,
              language: r.language,
              stars: r.stars,
              license: r.license,
              topics: r.topics.slice(0, 3),
              description: clean(r.description, 64)
            };
          })
        };
      });
    }
  });

  define({
    name: "get_repository",
    description: "Look up one repository by its full name (owner/name), or by its rank " +
      "within a language's top 100. Returns stars, forks, open issues, licence, last " +
      "push date, topics and description, plus links to its GitHub page and to the " +
      "language list it appears in.",
    inputSchema: {
      "type": "object",
      "properties": {
        "full_name": {
          "type": "string",
          "description": "owner/name, for example torvalds/linux.",
          "maxLength": 80
        },
        "language": {
          "type": "string",
          "description": "Language key, required together with rank.",
          "maxLength": 30
        },
        "rank": {
          "type": "integer",
          "minimum": 1,
          "maximum": 100,
          "description": "Position in that language's top 100, 1-100."
        }
      },
      "required": []
    },
    annotations: READ_ONLY_UNTRUSTED,
    pages: ["repos", "home"],
    timeoutMs: 15000,
    execute: function (args) {
      if (args.rank && !args.language) {
        throw new H.SiteError("INVALID_ARGUMENT", "Pass language together with rank.");
      }
      if (!args.rank && !args.full_name) {
        throw new H.SiteError("INVALID_ARGUMENT", "Pass full_name, or language and rank.");
      }
      var wanted = String(args.full_name || "").toLowerCase();

      // 1. The current page's embedded rows answer instantly and offline.
      var local = (Core.data.repos || []).filter(function (r) {
        return String(r.full_name).toLowerCase() === wanted;
      });
      var localLang = (Core.data.page || {}).language;
      if (!local.length && args.rank && localLang) {
        var lang = languageByKey(args.language);
        if (lang && lang.key === localLang) local = [(Core.data.repos || [])[args.rank - 1]].filter(Boolean);
      }

      function shape(r, rank, source) {
        return {
          rank: rank || null,
          source: source,
          full_name: clean(r.full_name, 80),
          url: clean(r.url || ("https://github.com/" + r.full_name), 120),
          language: clean(r.language || (languageByKey(args.language) || {}).key || "", 20),
          stars: Number(r.stars) || 0,
          forks: Number(r.forks) || 0,
          open_issues: Number(r.open_issues) || 0,
          license: clean(r.license || "NOASSERTION", 24),
          pushed_at: clean(r.pushed_at, 12),
          topics: (r.topics || []).slice(0, 8),
          description: clean(r.description, 140),
          language_page: H.languageUrl(r.language || args.language || "")
        };
      }

      if (local.length) {
        var index = (Core.data.repos || []).indexOf(local[0]);
        return shape(local[0], index >= 0 ? index + 1 : null, "current page");
      }

      return H.loadSearchIndex().then(function (index2) {
        var records = index2.repos.map(H.indexRecord).filter(Boolean);
        if (args.rank) {
          var lang = languageByKey(args.language);
          var inLang = records.filter(function (r) { return r.language === lang.key; });
          inLang.sort(function (a, b) { return b.stars - a.stars; });
          if (inLang[args.rank - 1]) {
            return shape(inLang[args.rank - 1], args.rank, "dataset rank");
          }
          throw new H.SiteError("NOT_FOUND", "That rank is outside the list.");
        }
        var hit = null;
        for (var i = 0; i < records.length; i += 1) {
          if (records[i].full_name.toLowerCase() === wanted) { hit = records[i]; break; }
        }
        if (!hit) {
          throw new H.SiteError("NOT_FOUND",
            "No repository in the dataset is named \"" + clean(args.full_name, 60) + "\".");
        }
        return shape(hit, null, "dataset");
      });
    }
  });

  define({
    name: "compare_repositories",
    description: "Compare two to five repositories side by side: stars, forks, open " +
      "issues, stars per fork, licence, last push and shared topics. Accepts owner/name " +
      "strings and returns them in the order given, with a one-line verdict naming the " +
      "leader by stars.",
    inputSchema: {
      "type": "object",
      "properties": {
        "repositories": {
          "type": "array",
          "items": { "type": "string", "maxLength": 80 },
          "minItems": 2,
          "maxItems": 5,
          "description": "Two to five repositories as owner/name."
        }
      },
      "required": ["repositories"]
    },
    annotations: READ_ONLY_UNTRUSTED,
    pages: ["repos", "home"],
    timeoutMs: 15000,
    execute: function (args) {
      return H.loadSearchIndex().then(function (index) {
        var records = index.repos.map(H.indexRecord).filter(Boolean);
        var byName = {};
        records.forEach(function (r) { byName[r.full_name.toLowerCase()] = r; });
        var rows = [];
        var missing = [];
        args.repositories.forEach(function (name) {
          var rec = byName[String(name).toLowerCase()];
          if (!rec) { missing.push(clean(name, 80)); return; }
          rows.push(rec);
        });
        if (rows.length < 2) {
          throw new H.SiteError("NOT_FOUND",
            "Fewer than two of those repositories are in the dataset.");
        }
        var shared = rows[0].topics.filter(function (topic) {
          return rows.every(function (r) {
            return r.topics.some(function (t) { return t.toLowerCase() === topic.toLowerCase(); });
          });
        });
        var leader = rows.slice().sort(function (a, b) { return b.stars - a.stars; })[0];
        return {
          compared: rows.map(function (r) {
            return {
              full_name: r.full_name,
              language: r.language,
              url: "https://github.com/" + r.full_name,
              stars: r.stars,
              forks: r.forks,
              open_issues: r.open_issues,
              stars_per_fork: r.forks ? Math.round(r.stars / r.forks) : null,
              license: r.license,
              pushed_at: r.pushed_at
            };
          }),
          shared_topics: shared.slice(0, 8),
          verdict: leader.full_name + " leads with " + fmt(leader.stars) + " stars.",
          not_in_dataset: missing
        };
      });
    }
  });

  define({
    name: "filter_repository_table",
    description: "Act on the visible page: filter the repository table by keyword, " +
      "licence, topic or minimum stars, then scroll it into view. Use reset to show " +
      "every row again. Returns how many rows matched, and the page visibly updates so " +
      "the human sees exactly what was filtered.",
    inputSchema: {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "Match repository name, description or topics.",
          "maxLength": 60,
          "default": ""
        },
        "license": {
          "type": "string",
          "description": "Keep only this SPDX licence id.",
          "maxLength": 30
        },
        "topic": {
          "type": "string",
          "description": "Keep only rows carrying this topic.",
          "maxLength": 40
        },
        "min_stars": {
          "type": "integer",
          "minimum": 0,
          "maximum": 1000000,
          "description": "Keep only rows with at least this many stars."
        },
        "reset": {
          "type": "boolean",
          "description": "Clear every filter and restore all rows.",
          "default": false
        }
      },
      "required": []
    },
    annotations: PAGE_ACTION_UNTRUSTED,
    pages: ["table"],
    execute: function (args) {
      var table = document.getElementById("repo-table");
      if (!table) throw new H.SiteError("NOT_FOUND", "This page has no repository table.");
      var rows = Array.prototype.slice.call(table.querySelectorAll("tbody tr"));
      var cleared = args.reset === true ||
        (!args.query && !args.license && !args.topic && typeof args.min_stars !== "number");
      var terms = String(args.query || "").toLowerCase().split(/\s+/)
        .filter(function (t) { return t.length > 1; }).slice(0, 6);
      var matched = 0;

      rows.forEach(function (row) {
        var haystack = (row.getAttribute("data-search") || "").toLowerCase();
        var license = (row.getAttribute("data-license") || "").toLowerCase();
        var stars = Number(row.getAttribute("data-stars") || 0);
        var topics = (row.getAttribute("data-topics") || "").toLowerCase();
        var keep = true;
        if (!cleared) {
          if (terms.some(function (term) { return haystack.indexOf(term) === -1; })) keep = false;
          if (args.license && license !== String(args.license).toLowerCase()) keep = false;
          if (args.topic && topics.split(/\s+/).indexOf(String(args.topic).toLowerCase()) === -1) keep = false;
          if (typeof args.min_stars === "number" && stars < args.min_stars) keep = false;
        }
        row.hidden = !keep;
        if (keep) matched += 1;
      });

      var banner = document.getElementById("repo-table-filter");
      if (banner) {
        banner.hidden = cleared;
        banner.textContent = cleared ? "" : "Filtered by an AI agent: " + matched +
          " of " + rows.length + " rows match" +
          (args.query ? " \u201c" + clean(args.query, 60).replace(/[<>]/g, "") + "\u201d" : "") +
          (args.license ? " \u00b7 licence " + clean(args.license, 30) : "") +
          (args.topic ? " \u00b7 topic " + clean(args.topic, 40) : "") +
          (typeof args.min_stars === "number" ? " \u00b7 \u2265" + fmt(args.min_stars) + " stars" : "");
      }
      if (!cleared) {
        var anchor = document.getElementById("repo-table-anchor") || table;
        if (typeof anchor.scrollIntoView === "function") {
          anchor.scrollIntoView({ block: "start", behavior: "smooth" });
        }
      }
      return {
        visible_rows: matched,
        total_rows: rows.length,
        filters: {
          query: clean(args.query || "", 60),
          license: clean(args.license || "", 30),
          topic: clean(args.topic || "", 40),
          min_stars: typeof args.min_stars === "number" ? args.min_stars : null,
          cleared: cleared
        },
        note: "The table on this page now shows these rows."
      };
    }
  });

  /* ===================================================================== *
   * 4. Navigation — always inside this site, always allowlisted.
   * ===================================================================== */

  define({
    name: "open_page",
    description: "Navigate the current tab to one of this site's own pages: home, the " +
      "language index, a specific language list, methodology, dataset reference, " +
      "comparison, FAQ or the WebMCP tools page. Only same-site pages can be opened; " +
      "the user sees the navigation happen.",
    inputSchema: {
      "type": "object",
      "properties": {
        "page": {
          "type": "string",
          "enum": ["home", "languages", "language", "methodology", "dataset", "compare", "faq", "webmcp"],
          "description": "Which page to open."
        },
        "language": {
          "type": "string",
          "description": "Language key, required when page is \"language\".",
          "maxLength": 30
        }
      },
      "required": ["page"]
    },
    annotations: PAGE_ACTION,
    pages: ["all"],
    execute: function (args) {
      var url;
      if (args.page === "language") {
        var lang = languageByKey(args.language);
        if (!lang) {
          throw new H.SiteError("NOT_FOUND", "Pass a tracked language key, for example python.");
        }
        url = H.languagePage(lang);
      } else {
        var routes = pageRoutes();
        url = routes[args.page];
        if (!url) throw new H.SiteError("NOT_FOUND", "That page does not exist on this site.");
      }
      if (!H.sameOrigin(url)) {
        throw new H.SiteError("INVALID_ARGUMENT", "Only same-site pages can be opened.");
      }
      var absolute = new URL(url, document.baseURI).href;
      // Navigation happens after the result is returned so the caller still
      // receives a well-formed envelope.
      setTimeout(function () {
        if (H.sameOrigin(absolute)) window.location.assign(absolute);
      }, 120);
      return {
        opened: clean(absolute, 200),
        page: clean(args.page, 40),
        note: "The browser is navigating to this page."
      };
    }
  });

  /* ===================================================================== *
   * 5. Documentation — methodology, dataset fields, comparison, FAQ.
   * ===================================================================== */

  define({
    name: "get_methodology",
    description: "Explain how the data is produced: the GitHub Search API query, the " +
      "hourly schedule, rate-limit handling, the fields the Search API omits, and the " +
      "known limitations. Called without arguments it returns the section ids, their " +
      "titles and the overview; call it again with one of those ids to read that " +
      "section in full.",
    inputSchema: {
      "type": "object",
      "properties": {
        "topic": {
          "type": "string",
          "description": "Section id from a previous call, for example limitations.",
          "maxLength": 60
        }
      },
      "required": []
    },
    annotations: READ_ONLY,
    pages: ["all"],
    execute: function (args) {
      return H.loadContext().then(function (context) {
        var docs = context.docs.filter(function (d) { return d.kind === "methodology"; });
        if (!docs.length) {
          throw new H.SiteError("DATA_UNAVAILABLE", "The methodology text is unavailable.");
        }
        if (args.topic) {
          var wanted = String(args.topic).toLowerCase();
          var hit = docs.filter(function (d) {
            return String(d.id).toLowerCase() === wanted ||
              String(d.title).toLowerCase().indexOf(wanted) !== -1;
          })[0];
          if (!hit) {
            throw new H.SiteError("NOT_FOUND", "No methodology section matched that topic id.");
          }
          return {
            sections: [{
              id: clean(hit.id, 60),
              title: clean(hit.title, 120),
              text: clean(hit.text, 900)
            }]
          };
        }
        var overview = docs.filter(function (d) { return d.id === "summary"; })[0];
        return {
          page: clean((Core.data.site || {}).base_url + "/methodology.html", 140),
          overview: clean(overview ? overview.text : "", 420),
          sections: docs.map(function (d) {
            return {
              id: clean(d.id, 60),
              title: clean(d.title, 120),
              characters: String(d.text || "").length
            };
          }),
          __notes: ["Call get_methodology again with topic=<id> to read a section."]
        };
      });
    }
  });

  define({
    name: "get_dataset_schema",
    description: "Document the JSONL dataset: one file per language, one complete GitHub " +
      "Search API repository object per line. Called without arguments it lists the field " +
      "names and types; call it with field=<name> to read what one field means, or with " +
      "language=<key> to get that file's download URL, size and SHA-256 checksum.",
    inputSchema: {
      "type": "object",
      "properties": {
        "field": {
          "type": "string",
          "description": "A field name such as stargazers_count or license.",
          "maxLength": 60
        },
        "language": {
          "type": "string",
          "description": "Return the download details for this language only.",
          "maxLength": 30
        }
      },
      "required": []
    },
    annotations: READ_ONLY,
    pages: ["all"],
    execute: function (args) {
      var site = Core.data.site || {};
      var langs = Core.data.languages || [];

      if (args.field) {
        var wanted = String(args.field).toLowerCase();
        return H.loadContext().then(function (context) {
          var hit = context.docs.filter(function (d) { return d.kind === "field"; })
            .filter(function (f) { return String(f.id).toLowerCase() === wanted; })[0];
          if (!hit) {
            throw new H.SiteError("NOT_FOUND", "No documented field matched that name.");
          }
          return {
            field: clean(hit.id, 60),
            type: clean(hit.type, 40),
            group: clean(hit.group || "", 60),
            meaning: clean(hit.text, 500),
            page: clean(site.base_url + "/dataset.html", 140)
          };
        });
      }

      var shape = {
        format: "newline-delimited JSON: one complete, unmodified GitHub Search API repository object per line",
        records_total: Number(site.records) || langs.length * 100,
        records_per_file: 100,
        encoding: "UTF-8",
        licence: "Repo metadata belongs to GitHub; each listed project keeps its own licence",
        page: clean(site.base_url + "/dataset.html", 140),
        example_query: "duckdb -c \"SELECT full_name, stargazers_count FROM read_json_auto('python.jsonl') LIMIT 10;\""
      };

      if (args.language) {
        var lang = languageByKey(args.language);
        if (!lang) throw new H.SiteError("NOT_FOUND", "No tracked language matched that name.");
        shape.file = {
          language: clean(lang.key, 20),
          jsonl_url: clean(lang.jsonl, 200),
          markdown_url: clean(lang.markdown, 200),
          records: 100,
          bytes: Number(lang.size_bytes) || 0,
          sha256: clean(lang.sha256, 64)
        };
        shape.__notes = ["Verify a download with: sha256sum " + clean(lang.key, 20) + ".jsonl"];
        return shape;
      }

      shape.data_files = {
        count: langs.length,
        total_bytes: Number(site.jsonl_bytes) || 0,
        path_pattern: "data/JSONL/<language>.jsonl in the source repository",
        checksums: clean(site.base_url + "/data/webmcp-manifest.json", 160)
      };
      shape.__notes = ["Pass language=<key> for one file's URL and checksum."];

      return H.loadContext().then(function (context) {
        var fields = context.docs.filter(function (d) { return d.kind === "field"; });
        shape.fields_total = fields.length;
        shape.fields = fields.slice(0, 12).map(function (f) {
          return { field: clean(f.id, 60), type: clean(f.type, 30) };
        });
        if (fields.length > 12) {
          shape.__notes = shape.__notes.concat(
            (fields.length - 12) + " more fields; call with field=<name> for the meaning.");
        }
        return shape;
      });
    }
  });

  define({
    name: "get_comparison",
    description: "Explain how Top100 differs from other GitHub ranking sources — GitHub " +
      "Trending, gitstar-ranking.com, EvanLi/Github-Ranking, OSS Insight, Star History, " +
      "GH Archive and BigQuery — including where each one is the better tool. Called " +
      "without arguments it lists the sources; pass one to read its full comparison.",
    inputSchema: {
      "type": "object",
      "properties": {
        "source": {
          "type": "string",
          "description": "One source name to compare against, for example GitHub Trending.",
          "maxLength": 60
        }
      },
      "required": []
    },
    annotations: READ_ONLY,
    pages: ["all"],
    execute: function (args) {
      return H.loadContext().then(function (context) {
        var entries = context.docs.filter(function (d) { return d.kind === "comparison"; });
        if (!entries.length) {
          throw new H.SiteError("DATA_UNAVAILABLE", "The comparison text is unavailable.");
        }
        var page = clean((Core.data.site || {}).base_url + "/compare.html", 140);
        if (args.source) {
          var wanted = String(args.source).toLowerCase();
          var hit = entries.filter(function (e) {
            return String(e.id).toLowerCase().indexOf(wanted) !== -1 ||
              String(e.title).toLowerCase().indexOf(wanted) !== -1;
          })[0];
          if (!hit) throw new H.SiteError("NOT_FOUND", "No comparison entry matched that source.");
          return {
            page: page,
            entries: [{ id: clean(hit.id, 60), title: clean(hit.title, 120), text: clean(hit.text, 900) }]
          };
        }
        return {
          page: page,
          sources: entries.map(function (e) {
            return { id: clean(e.id, 60), title: clean(e.title, 120) };
          }),
          __notes: ["Call get_comparison again with source=<id> to read one entry."]
        };
      });
    }
  });

  define({
    name: "answer_question",
    description: "Answer a question about this project from the site's own FAQ: refresh " +
      "cadence, licensing, whether it needs an API key, how to download the data, how to " +
      "add a language, why some fields are missing. Returns the closest matches with " +
      "their answers, ranked deterministically.",
    inputSchema: {
      "type": "object",
      "properties": {
        "question": {
          "type": "string",
          "description": "The user's question in natural language.",
          "maxLength": 200
        },
        "max_results": {
          "type": "integer",
          "minimum": 1,
          "maximum": 5,
          "description": "Matches to return, 1-5.",
          "default": 2
        }
      },
      "required": ["question"]
    },
    annotations: READ_ONLY,
    pages: ["all"],
    execute: function (args) {
      var limit = args.max_results || 2;
      var faqPage = clean((Core.data.site || {}).base_url + "/faq.html", 140);

      function shape(matches, source, total) {
        return {
          question: clean(args.question, 200),
          answered_from: source,
          matches: matches.map(function (m) {
            return { question: clean(m.q, 160), answer: clean(m.a, 420), score: m.score };
          }),
          faq_page: faqPage,
          __notes: total > matches.length
            ? [total + " FAQ entries matched; " + matches.length + " returned."]
            : []
        };
      }

      // The page's own FAQ entries answer instantly; the shared context file
      // covers the pages that do not embed any.
      var local = H.answerLookup(args.question, limit);
      if (local.length) return shape(local, "this page's FAQ section", local.length);
      return H.loadContext().then(function (context) {
        var matches = H.answerLookup(args.question, limit, context.faq);
        if (!matches.length) {
          throw new H.SiteError("NOT_FOUND",
            "No FAQ entry matched that question. Try get_methodology or get_dataset_schema.");
        }
        return shape(matches, context.faq.length + " site FAQ entries", context.faq.length);
      });
    }
  });

  /* ===================================================================== *
   * 6. Diagnostics — opt-in, marked debugging so user-facing agents skip it.
   * ===================================================================== */

  define({
    name: "run_webmcp_self_test",
    description: "Run this page's own WebMCP checks: page data present, tools " +
      "registered, character budgets respected, prototype pollution rejected, output " +
      "budget enforced, and every registered tool answering a call with a structured " +
      "envelope. Intended for developers and test harnesses.",
    inputSchema: {
      "type": "object",
      "properties": {},
      "required": []
    },
    annotations: DEBUG_ONLY,
    pages: ["all"],
    timeoutMs: 15000,
    execute: function () {
      return Core.selfTest().then(function (report) {
        return {
          summary: report.passed + " of " + (report.passed + report.failed) + " checks passed",
          checks: report.checks.slice(0, 12).map(function (c) {
            return { check: clean(c.check, 60), ok: c.ok, detail: clean(c.detail, 80) };
          }),
          failed: report.failed
        };
      });
    }
  });

  /* ===================================================================== *
   * Hand over to the core: it applies each tool's `pages` scope to this
   * document, registers what fits, wires the status line and — with
   * ?webmcp_debug=1 — the debug panel.
   * ===================================================================== */

  Core.start();
})();
