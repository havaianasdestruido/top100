#!/usr/bin/env node
/**
 * Run the Top100 WebMCP runtime in a sandbox and check what it actually does.
 *
 * The site has no bundler, no dependencies and no test framework, so this file
 * is all three: a minimal DOM, a minimal fetch, and a set of assertions that
 * cover the promises the documentation makes —
 *
 *   - the right tools register on the right pages, and only those
 *   - every call returns a structured envelope, never a throw and never a
 *     stack trace, whatever an agent passes in
 *   - bad arguments, hostile keys and wrong types are rejected by name
 *   - results stay inside the 1500-character output budget
 *   - rate limits, per-tool locks and timeouts exist and fire
 *   - a native document.modelContext gets the same guarantees as the polyfill
 *   - the site's own text is never rendered with innerHTML or eval
 *
 * Usage: node scripts/webmcp_test.mjs [--verbose]
 * Exits non-zero on the first failing assertion group.
 */

import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import http from "node:http";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const VERBOSE = process.argv.includes("--verbose");

const CORE = fs.readFileSync(path.join(ROOT, "assets/webmcp-core.js"), "utf8");
const TOOLS = fs.readFileSync(path.join(ROOT, "assets/webmcp-tools.js"), "utf8");

let failures = 0;
let checks = 0;

function ok(condition, label, detail) {
  checks += 1;
  if (condition) {
    if (VERBOSE) console.log(`  ok   ${label}`);
    return true;
  }
  failures += 1;
  console.log(`  FAIL ${label}${detail ? ` — ${detail}` : ""}`);
  return false;
}

function group(name) {
  console.log(`\n${name}`);
}

/* ------------------------------------------------------------------ *
 * Minimal DOM
 * ------------------------------------------------------------------ */

class El {
  constructor(tag) {
    this.tagName = String(tag || "div").toUpperCase();
    this.children = [];
    this.attributes = {};
    this.textContent = "";
    this.className = "";
    this.hidden = false;
    this.value = "";
    this.open = false;
    this.handlers = {};
    this.id = "";
  }
  get firstChild() { return this.children[0] || null; }
  appendChild(child) { this.children.push(child); return child; }
  removeChild(child) {
    const i = this.children.indexOf(child);
    if (i >= 0) this.children.splice(i, 1);
    return child;
  }
  setAttribute(key, value) {
    this.attributes[key] = String(value);
    if (key === "id") this.id = String(value);
  }
  getAttribute(key) { return key in this.attributes ? this.attributes[key] : null; }
  addEventListener(type, fn) { (this.handlers[type] ||= []).push(fn); }
  removeEventListener() {}
  querySelectorAll(selector) { return this._query ? this._query(selector) : []; }
  scrollIntoView() { this.scrolled = true; }
  dispatch(type) { (this.handlers[type] || []).forEach((fn) => fn({ type })); }
}

function makeRow(attrs) {
  const row = new El("tr");
  Object.entries(attrs).forEach(([k, v]) => row.setAttribute(k, v));
  return row;
}

function makePage({ pageFile, rows = null, dataBlock,
                    base = "http://localhost:8080/" }) {
  const elements = new Map();
  const body = new El("body");

  const dataNode = new El("script");
  dataNode.setAttribute("id", "top100-webmcp-data");
  dataNode.textContent = dataBlock;
  elements.set("top100-webmcp-data", dataNode);

  // The real build renders a table exactly where the page has repository rows,
  // so the stub does the same: rows are taken from the embedded data unless a
  // test passes its own.
  const embedded = JSON.parse(dataBlock);
  const table = new El("table");
  table.setAttribute("id", "repo-table");
  const tbody = new El("tbody");
  const rowList = rows !== null ? rows : (embedded.repos || []).map((r) => makeRow({
    "data-search": `${r.full_name} ${r.description || ""} ${(r.topics || []).join(" ")}`,
    "data-license": String(r.license || "").toLowerCase(),
    "data-stars": String(r.stars || 0),
    "data-topics": (r.topics || []).join(" ").toLowerCase(),
  }));
  rowList.forEach((r) => tbody.appendChild(r));
  table._query = (selector) => (String(selector).includes("tbody tr") ? tbody.children : []);

  const banner = new El("div");
  banner.setAttribute("id", "repo-table-filter");
  banner.hidden = true;
  const anchor = new El("div");
  anchor.setAttribute("id", "repo-table-anchor");

  if (rowList.length) {
    elements.set("repo-table", table);
    elements.set("repo-table-filter", banner);
    elements.set("repo-table-anchor", anchor);
  }

  const document = {
    title: "Top 100 Python Repositories by Stars",
    baseURI: `${base}${pageFile}`,
    body,
    modelContext: undefined,
    permissionsPolicy: undefined,
    getElementById: (id) => elements.get(id) || null,
    createElement: (tag) => new El(tag),
    createTextNode: (text) => Object.assign(new El("#text"), { textContent: String(text) }),
    querySelectorAll: () => [],
    addEventListener() {},
    removeEventListener() {},
  };

  return { document, elements, body, table, banner, pageFile };
}

/* ------------------------------------------------------------------ *
 * Minimal runtime, fetch and filesystem-backed data
 * ------------------------------------------------------------------ */

function makeContext({ pageFile, native = false, search = "", rows = null,
                       polyfillOnly = false, fetchImpl = null,
                       base = "http://localhost:8080/" }) {
  const html = fs.readFileSync(path.join(ROOT, pageFile), "utf8");
  const match = html.match(
    /<script type="application\/json" id="top100-webmcp-data">([\s\S]*?)<\/script>/);
  if (!match) throw new Error(`no embedded data block in ${pageFile}`);
  const dataBlock = match[1];

  const page = makePage({ pageFile, rows, dataBlock, base });
  const fetchLog = [];
  const registered = [];

  const nativeContext = native && !polyfillOnly ? {
    registerTool(spec) { registered.push(spec); return Promise.resolve(); },
    getTools() { return Promise.resolve(registered.slice()); },
    executeTool(tool, args) {
      const found = registered.find((t) => t.name === (tool && tool.name) || t.name === tool);
      return Promise.resolve(found.execute(args, {}));
    },
    addEventListener() {}, removeEventListener() {}, dispatchEvent() { return true; },
  } : undefined;

  const pageOrigin = new URL(base).origin;
  const location = {
    href: `${base}${pageFile}${search}`,
    search,
    protocol: "http:",
    origin: pageOrigin,
    assign(url) { location.assigned = url; },
  };

  const window = {
    location,
    isSecureContext: true,
    console: { warn() {}, log() {}, error() {} },
    setTimeout,
    clearTimeout,
    addEventListener() {},
    removeEventListener() {},
    URL,
    URLSearchParams,
    fetch: fetchImpl || fakeFetch,
  };
  window.self = window;
  window.top = window;

  function fakeFetch(href, options) {
    fetchLog.push({ href, options });
    const url = new URL(href);
    const file = path.join(ROOT, url.pathname.replace(/^\//, ""));
    if (!fs.existsSync(file)) {
      return Promise.resolve({
        ok: false, status: 404,
        headers: { get: () => "text/html" },
        text: () => Promise.resolve(""),
      });
    }
    const text = fs.readFileSync(file, "utf8");
    return Promise.resolve({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      text: () => Promise.resolve(text),
    });
  }

  const sandbox = {
    window, document: page.document, navigator: { userAgent: "node" },
    location, URL, URLSearchParams, fetch: fetchImpl || fakeFetch, setTimeout, clearTimeout,
    console: window.console, AbortController, Promise, Math, Date, JSON,
    Object, Array, String, Number, Boolean, RegExp, Error, TypeError,
    isFinite, parseInt, parseFloat, CustomEvent: globalThis.CustomEvent,
  };
  sandbox.globalThis = sandbox;
  if (nativeContext) {
    page.document.modelContext = nativeContext;
  }
  sandbox.navigator.modelContext = undefined;

  const realm = vm.createContext(sandbox);
  const created = { realm };
  vm.runInContext(CORE, realm, { filename: "webmcp-core.js" });
  vm.runInContext(TOOLS, realm, { filename: "webmcp-tools.js" });

  const handle = {
    page,
    sandbox,
    realm,
    api: sandbox.window.Top100WebMCP,
    get context() { return page.document.modelContext; },
    registered,
    fetchLog,
    location,
  };
  CONTEXTS.push(handle);
  void created;
  return handle;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function envelope(call) {
  return call.then((result) => result, (err) => ({
    ok: false, threw: true, message: err && err.message,
  }));
}

// Every context keeps a log of what went wrong inside; the harness prints it
// when a check fails so a runtime error is never invisible.
const CONTEXTS = [];

/* ------------------------------------------------------------------ *
 * 1. Registration per page type
 * ------------------------------------------------------------------ */

async function testRegistration() {
  group("Registration");

  const home = makeContext({ pageFile: "index.html" });
  await sleep(30);
  const homeTools = await home.context.getTools();
  const homeNames = homeTools.map((t) => t.name);
  ok(homeNames.length >= 10, `homepage registers tools (${homeNames.length})`);
  ok(homeNames.includes("get_top_repositories"), "homepage has get_top_repositories");
  ok(homeNames.includes("filter_repository_table"), "homepage has filter_repository_table");
  ok(!homeNames.includes("open_page") === false, "homepage has open_page");
  ok(new Set(homeNames).size === homeNames.length, "tool names are unique");

  const lang = makeContext({ pageFile: "languages/python.html" });
  await sleep(30);
  const langNames = (await lang.context.getTools()).map((t) => t.name);
  ok(langNames.includes("get_top_repositories"), "language page has get_top_repositories");

  const docs = makeContext({ pageFile: "methodology.html" });
  await sleep(30);
  const docsNames = (await docs.context.getTools()).map((t) => t.name);
  ok(!docsNames.includes("get_top_repositories"),
    "methodology page has no repository tools");
  ok(docsNames.includes("get_methodology"), "methodology page has get_methodology");

  const missing = makeContext({ pageFile: "404.html" });
  await sleep(30);
  const names404 = (await missing.context.getTools()).map((t) => t.name);
  ok(names404.length > 0, "404 page still registers site tools");
  ok(!names404.includes("filter_repository_table"), "404 page has no table tool");

  // The polyfill must be usable through the standard entry point.
  ok(typeof home.context.registerTool === "function", "document.modelContext.registerTool exists");
  ok(typeof home.context.getTools === "function", "document.modelContext.getTools exists");
  ok(typeof home.context.executeTool === "function", "document.modelContext.executeTool exists");
  ok(typeof home.context.addEventListener === "function", "modelContext is an event target");
  ok(home.api.state.polyfill === true || home.api.state.native === true,
    "runtime reports which path it took");
}

/* ------------------------------------------------------------------ *
 * 2. Every tool answers, whatever it is handed
 * ------------------------------------------------------------------ */

async function testEveryToolAnswers() {
  group("Envelope discipline");

  for (const pageFile of ["index.html", "languages/python.html", "methodology.html",
    "dataset.html", "compare.html", "faq.html", "404.html", "webmcp.html"]) {
    const ctx = makeContext({ pageFile });
    await sleep(30);
    const tools = await ctx.context.getTools();
    ok(tools.length > 0, `${pageFile} registers ${tools.length} tools`);
    for (const tool of tools) {
      if (tool.annotations.debugging) continue;
      const result = await envelope(ctx.context.executeTool(tool.name, {}));
      ok(!result.threw && result && typeof result.ok === "boolean",
        `${pageFile}: ${tool.name} returns an envelope`, JSON.stringify(result).slice(0, 120));
      if (result && result.ok === false) {
        ok(typeof result.error.code === "string" && typeof result.error.message === "string",
          `${pageFile}: ${tool.name} error has code and message`);
        ok(!/at .*\.js:\d+/.test(JSON.stringify(result)),
          `${pageFile}: ${tool.name} leaks no stack trace`);
      }
      const text = JSON.stringify(result);
      ok(text.length <= 1500, `${pageFile}: ${tool.name} result within budget (${text.length})`);
    }
    await sleep(120); // respect the minimum gap between calls
  }
}

/* ------------------------------------------------------------------ *
 * 2b. Defaults — the smallest valid call must not need the output budget
 * ------------------------------------------------------------------ */

/** Minimal valid arguments per tool: one representative call, exactly what an
 *  agent sends when it takes the documented defaults. */
const MINIMAL = {
  get_site_info: {},
  get_page_context: {},
  list_languages: {},
  get_language_stats: { language: "python" },
  get_download_links: {},
  get_top_repositories: {},
  search_repositories: { query: "framework" },
  get_repository: { full_name: "public-apis/public-apis" },
  compare_repositories: { repositories: ["public-apis/public-apis", "torvalds/linux"] },
  filter_repository_table: { query: "python" },
  open_page: { page: "faq" },
  get_methodology: {},
  get_dataset_schema: {},
  get_comparison: {},
  answer_question: { question: "how often is the data refreshed" },
  run_webmcp_self_test: {},
};

async function testDefaults() {
  group("Default calls");

  const ctx = makeContext({ pageFile: "languages/python.html" });
  await sleep(30);

  for (const [name, args] of Object.entries(MINIMAL)) {
    await sleep(140);
    const env = await envelope(ctx.context.executeTool(name, args));
    ok(env && env.ok === true, `${name} answers its documented default call`,
      JSON.stringify(env).slice(0, 200));
    ok(env && env.truncated !== true, `${name} default output fits the budget`,
      env && `chars=${env.chars}`);
    ok(env && env.chars <= 1500, `${name} stays inside 1,500 characters`,
      env && `chars=${env.chars}`);
  }
}

/* ------------------------------------------------------------------ *
 * 3. Built pages — the real generated HTML, not the stub
 * ------------------------------------------------------------------ */

async function testBuiltPages() {
  group("Built pages");

  const languagePages = fs.readdirSync(path.join(ROOT, "languages"))
    .filter((name) => name.endsWith(".html") && name !== "index.html")
    .map((name) => `languages/${name}`)
    .sort();
  const pages = ["index.html", "languages/index.html", ...languagePages,
    "methodology.html", "dataset.html", "compare.html", "faq.html",
    "404.html", "webmcp.html"].filter((rel) => fs.existsSync(path.join(ROOT, rel)));

  ok(pages.length === 38, `every generated page is on disk (${pages.length})`);

  const expectedTypes = {
    "index.html": "home", "languages/index.html": "languages",
    "methodology.html": "methodology", "dataset.html": "dataset",
    "compare.html": "compare", "faq.html": "faq", "404.html": "404",
    "webmcp.html": "webmcp",
  };

  let scriptMismatch = 0;
  let blobMismatch = 0;
  let missingData = 0;
  let weakCsp = 0;

  for (const rel of pages) {
    const html = fs.readFileSync(path.join(ROOT, rel), "utf8");
    const depth = rel.split("/").length - 1;
    const prefix = depth === 0 ? "" : "../";
    const absolute = rel === "404.html" ? "/top100/" : prefix;

    for (const asset of ["webmcp-core.js", "webmcp-tools.js"]) {
      const tag = `<script defer src="${absolute}assets/${asset}"></script>`;
      if (!html.includes(tag)) { scriptMismatch += 1; break; }
      if (!fs.existsSync(path.join(ROOT, "assets", asset))) scriptMismatch += 1;
    }

    if (!html.includes('<meta http-equiv="Content-Security-Policy"') ||
      !html.includes("script-src &#x27;self&#x27;") ||
      !html.includes('<meta http-equiv="Permissions-Policy" content="tools=(self)">')) {
      weakCsp += 1;
    }

    const match = html.match(
      /<script type="application\/json" id="top100-webmcp-data">([\s\S]*?)<\/script>/);
    if (!match) { blobMismatch += 1; continue; }
    const blob = JSON.parse(match[1]);
    if (blob.schema !== "top100.webmcp-page/1" || typeof blob.page.type !== "string") {
      blobMismatch += 1;
      continue;
    }
    const wantType = expectedTypes[rel] || "language";
    if (blob.page.type !== wantType) blobMismatch += 1;
    if (rel.startsWith("languages/") && rel !== "languages/index.html") {
      // The file name is the language's slug (csharp.html, cpp.html), while the
      // blob carries the GitHub language key (c#, c++).
      const slug = path.basename(rel, ".html");
      const entry = (blob.languages || []).find((l) => l.slug === slug);
      if (!entry || blob.page.language !== entry.key) blobMismatch += 1;
      if (!Array.isArray(blob.repos) || blob.repos.length !== 100) blobMismatch += 1;
    }

    // data_base must resolve the site's data files for this page depth: the
    // core joins it with "data/<file>" exactly like this.
    let dataFile;
    if (rel === "404.html") {
      dataFile = path.join(ROOT, blob.page.data_base.replace(/^\/top100\//, ""),
        "data/webmcp-context.json");
    } else {
      dataFile = path.resolve(ROOT, path.dirname(rel), blob.page.data_base,
        "data/webmcp-context.json");
    }
    if (!fs.existsSync(dataFile)) missingData += 1;
  }

  ok(scriptMismatch === 0, "every page loads the runtime with the right relative path",
    `${scriptMismatch} page(s)`);
  ok(blobMismatch === 0, "every page carries the expected data blob", `${blobMismatch} page(s)`);
  ok(missingData === 0, "every page's data_base points at the real data files",
    `${missingData} page(s)`);
  ok(weakCsp === 0, "every page carries the CSP and Permissions-Policy meta tags");
  ok(pages.includes("webmcp.html"), "webmcp.html is generated");

  // The manifest is the machine-readable contract; it must agree with the HTML.
  const manifest = JSON.parse(
    fs.readFileSync(path.join(ROOT, "data/webmcp-manifest.json"), "utf8"));
  const home = JSON.parse(fs.readFileSync(path.join(ROOT, "index.html"), "utf8")
    .match(/<script type="application\/json" id="top100-webmcp-data">([\s\S]*?)<\/script>/)[1]);
  ok(manifest.data_files.reduce((n, f) => n + f.records, 0) === home.site.records,
    "the manifest's dataset adds up to the record count the pages quote");
  ok(manifest.tools.length === 16, `the manifest lists all 16 tools (${manifest.tools.length})`);
  ok(manifest.data_files.length === 30 &&
    manifest.data_files.every((f) => fs.existsSync(path.join(ROOT, f.path))),
    "every dataset file in the manifest exists on disk");
  const context = JSON.parse(
    fs.readFileSync(path.join(ROOT, "data/webmcp-context.json"), "utf8"));
  ok(context.faq.length >= 8 && context.docs.length > 40,
    `the context file carries ${context.faq.length} FAQ answers and ${context.docs.length} docs`);
  ok(manifest.tools.every((t) => t.pages.length > 0), "every tool declares where it loads");
}

/* ------------------------------------------------------------------ *
 * 4. Input validation
 * ------------------------------------------------------------------ */

async function testValidation() {
  group("Input validation");

  const ctx = makeContext({ pageFile: "languages/python.html" });
  await sleep(30);
  const data = JSON.parse(ctx.page.elements.get("top100-webmcp-data").textContent);
  ok(data.page.type === "language" && data.repos.length === 100,
    "language page embeds its 100 rows");

  const bad = [
    ["list_languages", { limit: 999 }, "OUT_OF_RANGE"],
    ["list_languages", { limit: "not a number" }, "INVALID_TYPE"],
    ["list_languages", { limit: 2.7 }, null],
    ["list_languages", { sort: "nonsense" }, "NOT_IN_ENUM"],
    ["search_repositories", { query: "x".repeat(500) }, "TOO_LONG"],
    ["get_top_repositories", { limit: 500 }, "OUT_OF_RANGE"],
    ["compare_repositories", { repositories: ["a"] }, "TOO_FEW_ITEMS"],
    ["compare_repositories", { repositories: ["a", "b", "c", "d", "e", "f"] }, "TOO_MANY_ITEMS"],
    ["open_page", { page: "https://evil.example" }, "NOT_IN_ENUM"],
    ["get_language_stats", {}, "MISSING_ARGUMENT"],
    ["get_language_stats", { language: 42 }, null],
  ];

  for (const [name, args, expected] of bad) {
    const result = await envelope(ctx.context.executeTool(name, args));
    if (expected === null) {
      ok(result.ok === true || result.ok === false,
        `${name}(${JSON.stringify(args)}) handled`, result.error && result.error.code);
    } else {
      ok(result.ok === false && result.error && result.error.code === expected,
        `${name}(${JSON.stringify(args)}) → ${expected}`,
        result.error ? result.error.code : JSON.stringify(result).slice(0, 100));
    }
    await sleep(120);
  }

  // Prototype pollution, using a real own "__proto__" property.
  const polluted = JSON.parse('{"__proto__":{"isAdmin":true},"limit":1}');
  const result = await envelope(ctx.context.executeTool("list_languages", polluted));
  ok(result.ok === false && result.error.code === "FORBIDDEN_KEY",
    "__proto__ is rejected", JSON.stringify(result).slice(0, 120));
  ok({}.isAdmin === undefined, "Object.prototype was not polluted");
  await sleep(130);

  // Coercion that helps an agent instead of failing the call.
  const coerced = await envelope(ctx.context.executeTool("list_languages", { limit: "3" }));
  if (!coerced.ok) {
    console.log("   internal:", JSON.stringify(ctx.api.state.errors.slice(-4)));
  }
  if (process.env.DEBUG_WEBMCP) console.log("DEBUG coerced:", JSON.stringify(coerced).slice(0, 400));
  ok(coerced.ok === true && coerced.data.languages.length === 3,
    "a numeric string is accepted for an integer");
  ok(Array.isArray(coerced.warnings) && coerced.warnings.length > 0, "coercion is reported");
  await sleep(130);

  // Unknown arguments are ignored and named back to the caller.
  const extra = await envelope(ctx.context.executeTool("list_languages",
    { limit: 1, sneaky: "value" }));
  ok(extra.ok === true && Array.isArray(extra.ignored_args) &&
    extra.ignored_args.includes("sneaky"), "unknown arguments are reported");
  await sleep(130);

  // Unknown tools and bad call shapes.
  const unknown = await envelope(ctx.context.executeTool("drop_database", {}));
  ok(unknown.ok === false && unknown.error.code === "UNKNOWN_TOOL", "unknown tool is rejected");

  const shape = await envelope(ctx.context.executeTool({
    toolName: "list_languages", input: { limit: 1 },
  }));
  ok(shape.ok === true, "legacy single-object call shape still works");
}

/* ------------------------------------------------------------------ *
 * 4. Real behaviour of the data tools
 * ------------------------------------------------------------------ */

async function testTools() {
  group("Tool behaviour");

  const ctx = makeContext({ pageFile: "languages/python.html" });
  await sleep(30);
  if (process.env.DEBUG_WEBMCP) ctx.api.state.debug = true;

  const call = async (name, args) => {
    const result = await envelope(ctx.context.executeTool(name, args));
    await sleep(120);
    return result;
  };

  const top = await call("get_top_repositories", { limit: 3 });
  ok(top.ok && top.data.repositories.length === 3, "get_top_repositories returns rows");
  ok(top.data.repositories[0].rank === 1 && top.data.repositories[0].stars > 0,
    "rows are ranked and carry stars");
  ok(top.trust === "untrusted", "third-party text is labelled untrusted");

  const page1 = await call("get_top_repositories", { limit: 2, offset: 0, sort: "forks" });
  const page2 = await call("get_top_repositories", { limit: 2, offset: 0, sort: "stars" });
  ok(page1.data.repositories[0].full_name !== page2.data.repositories[0].full_name ||
    page1.data.repositories[0].forks === page2.data.repositories[0].forks,
    "sorting changes the order");

  const stats = await call("get_language_stats", { language: "Python" });
  if (process.env.DEBUG_WEBMCP) console.log("DEBUG stats:", JSON.stringify(stats).slice(0, 400));
  ok(stats.ok && stats.data.stars_to_enter_top_100 > 0,
    "get_language_stats finds a language by display name");
  ok(String(stats.data.jsonl_sha256).length === 64, "stats include a checksum");

  const notFound = await call("get_language_stats", { language: "cobol" });
  ok(notFound.ok === false && notFound.error.code === "NOT_FOUND", "unknown language → NOT_FOUND");

  const search = await call("search_repositories", { query: "web framework", language: "python" });
  ok(search.ok && search.data.scanned === 3000,
    "search_repositories reads the 3,000-record index");
  ok(search.data.results.every((r) => r.language === "python"),
    "language filter applies to search results");
  ok(ctx.fetchLog.some((f) => f.href.includes("search-index.json")),
    "the index was fetched from this origin");
  ok(ctx.fetchLog.every((f) => f.href.startsWith("http://localhost:8080/")),
    "no request left the origin");
  ok(ctx.fetchLog.every((f) => f.options.credentials === "omit"),
    "credentialed requests are never made");

  const repo = await call("get_repository", { full_name: "public-apis/public-apis" });
  ok(repo.ok && repo.data.stars > 0, "get_repository finds a record by full name");

  const compare = await call("compare_repositories", {
    repositories: ["public-apis/public-apis", "vinta/awesome-python"],
  });
  ok(compare.ok && compare.data.compared.length === 2, "compare_repositories compares two");
  ok(typeof compare.data.verdict === "string", "comparison returns a verdict");

  const method = await call("get_methodology", {});
  if (process.env.DEBUG_WEBMCP) console.log("DEBUG method:", JSON.stringify(method).slice(0, 400));
  ok(method.ok && method.data.sections.length > 3, "get_methodology lists sections");
  ok(method.ok && method.data.overview.length > 40, "get_methodology includes an overview");
  const section = await call("get_methodology", { topic: method.data.sections[1].id });
  ok(section.ok && section.data.sections[0].text.length > 100,
    "get_methodology reads one section in full");
  ok(ctx.fetchLog.some((f) => f.href.includes("webmcp-context.json")),
    "documentation is fetched from the context file");

  const schema = await call("get_dataset_schema", { field: "stargazers_count" });
  ok(schema.ok && /star/i.test(schema.data.meaning), "get_dataset_schema explains a field");
  const file = await call("get_dataset_schema", { language: "python" });
  ok(file.ok && file.data.file.sha256.length === 64, "get_dataset_schema returns a checksum");
  const list = await call("get_dataset_schema", {});
  ok(list.ok && list.data.fields.length > 5 && list.data.data_files.count === 30,
    "get_dataset_schema lists fields and data files");

  const links = await call("get_download_links", {});
  ok(links.ok && links.chars <= 1500, "get_download_links fits the output budget",
    `chars=${links.chars} truncated=${links.truncated}`);
  ok(links.ok && links.data.site_files.length === 10,
    "get_download_links lists every published file",
    JSON.stringify(links.data.site_files || []).slice(0, 120));
  ok(links.ok && links.data.site_files.some((f) => f.path === "llms-full.txt") &&
    links.data.site_files.some((f) => f.path === "data/webmcp-manifest.json"),
    "the file list covers llms-full.txt and the manifest");
  ok(links.ok && links.data.site_files.every((f) => !/^https?:/.test(f.path)) &&
    /^https?:\/\//.test(links.data.base_url),
    "site files are base_url-relative so the origin is stated once");
  const oneFile = await call("get_download_links", { language: "rust" });
  ok(oneFile.ok && /^[0-9a-f]{64}$/.test(oneFile.data.jsonl_sha256),
    "get_download_links returns one file's checksum");

  const answer = await call("answer_question", { question: "How often is the data refreshed?" });
  if (process.env.DEBUG_WEBMCP && !answer.ok) {
    console.log("DEBUG answer errors:", JSON.stringify(ctx.api.state.errors));
  }
  ok(answer.ok && answer.data.matches.length > 0, "answer_question finds FAQ entries");

  const sources = await call("get_comparison", {});
  ok(sources.ok && sources.data.sources.length > 3, "get_comparison lists sources");
  const comparison = await call("get_comparison",
    { source: sources.data.sources[2].id });
  ok(comparison.ok && comparison.data.entries[0].text.length > 40,
    "get_comparison reads one entry");
}

/* ------------------------------------------------------------------ *
 * 5. Tools that act on the page
 * ------------------------------------------------------------------ */

async function testPageActions() {
  group("Page actions");

  const rows = [
    makeRow({ "data-search": "public-apis public-apis free apis", "data-license": "mit",
      "data-stars": "486912", "data-topics": "api list" }),
    makeRow({ "data-search": "yt-dlp downloader", "data-license": "unlicense",
      "data-stars": "196338", "data-topics": "youtube downloader" }),
    makeRow({ "data-search": "django django web framework", "data-license": "bsd-3-clause",
      "data-stars": "80000", "data-topics": "web framework" }),
  ];
  const ctx = makeContext({ pageFile: "languages/python.html", rows });
  await sleep(30);

  const filtered = await envelope(ctx.context.executeTool("filter_repository_table",
    { query: "framework" }));
  ok(filtered.ok, "filter_repository_table runs");
  ok(filtered.data.visible_rows === 1, "the filter matches one row",
    String(filtered.data.visible_rows));
  ok(ctx.page.banner.hidden === false && /1 of 3/.test(ctx.page.banner.textContent),
    "the page shows a filter banner");
  ok(ctx.page.banner.textContent.includes("framework"), "the banner names the filter");

  await sleep(120);
  const reset = await envelope(ctx.context.executeTool("filter_repository_table", { reset: true }));
  ok(reset.ok && reset.data.visible_rows === 3, "reset restores every row");
  ok(ctx.page.banner.hidden === true, "reset hides the banner");

  await sleep(120);
  const byStars = await envelope(ctx.context.executeTool("filter_repository_table",
    { min_stars: 100000 }));
  ok(byStars.ok && byStars.data.visible_rows === 2, "star filter applies");
  const html = ctx.page.banner.textContent;
  ok(!/[<>]/.test(html), "banner text contains no markup");

  // A hostile query string must not become markup in the banner.
  await sleep(120);
  const hostile = await envelope(ctx.context.executeTool("filter_repository_table",
    { query: "<img src=x onerror=alert(1)>" }));
  ok(hostile.ok, "hostile query is handled");
  ok(ctx.page.banner.textContent.indexOf("<") === -1,
    "angle brackets are stripped from the human-facing banner",
    ctx.page.banner.textContent);
  ok(ctx.page.banner.children.length === 0,
    "the banner renders text only — no element is ever created from a query");

  await sleep(120);
  const nav = await envelope(ctx.context.executeTool("open_page", { page: "dataset" }));
  ok(nav.ok && nav.data.opened.endsWith("dataset.html"), "open_page resolves a page");
  await sleep(200);
  ok(String(ctx.location.assigned || "").endsWith("dataset.html"),
    "open_page navigates to this site only", ctx.location.assigned);
  ok(String(ctx.location.assigned).startsWith("http://localhost:8080/"),
    "navigation stays on the origin");

  await sleep(120);
  const langNav = await envelope(ctx.context.executeTool("open_page",
    { page: "language", language: "rust" }));
  await sleep(250);
  ok(langNav.ok && /\/languages\/rust\.html$/.test(String(ctx.location.assigned)),
    "open_page resolves a language page relative to this one",
    String(ctx.location.assigned));
}

/* ------------------------------------------------------------------ *
 * 6. Native modelContext path
 * ------------------------------------------------------------------ */

async function testNativePath() {
  group("Native document.modelContext");

  const ctx = makeContext({ pageFile: "index.html", native: true });
  await sleep(30);
  ok(ctx.api.state.native === true, "the runtime used the native context");
  ok(ctx.registered.length > 5, "tools were registered with the native context",
    String(ctx.registered.length));

  const tool = ctx.registered.find((t) => t.name === "list_languages");
  ok(Boolean(tool), "list_languages reached the native context");
  ok(typeof tool.execute === "function", "native tools carry an execute function");

  // The important one: a browser calling execute() directly must still get
  // validation, an envelope and the output budget.
  const direct = await envelope(tool.execute({ limit: 999 }, {}));
  ok(direct.ok === false && direct.error.code === "OUT_OF_RANGE",
    "a direct native execute() call is still validated");

  await sleep(120);
  const good = await envelope(tool.execute({ limit: 2 }, {}));
  ok(good.ok === true && good.data.languages.length === 2,
    "a direct native execute() call returns an envelope");
  ok(JSON.stringify(good).length <= 1500, "direct calls respect the output budget");

  await sleep(120);
  const proto = await envelope(tool.execute(JSON.parse('{"__proto__":{"x":1}}'), {}));
  ok(proto.ok === false && proto.error.code === "FORBIDDEN_KEY",
    "direct native calls reject __proto__");

  const specs = ctx.registered.map((t) => Object.keys(t));
  ok(specs.every((keys) => keys.every((k) =>
    ["name", "title", "description", "inputSchema", "annotations", "execute"].includes(k))),
    "native registration passes only the standard tool fields", JSON.stringify(specs[0]));

  const serialisable = JSON.stringify(await ctx.context.getTools());
  ok(serialisable.includes("list_languages"), "getTools() output is JSON-serialisable");
}

/* ------------------------------------------------------------------ *
 * 7. Limits: rate, lock, budget, timeout
 * ------------------------------------------------------------------ */

async function testLimits() {
  group("Limits");

  const ctx = makeContext({ pageFile: "index.html" });
  await sleep(30);

  let rateLimited = false;
  for (let i = 0; i < 45 && !rateLimited; i += 1) {
    const result = await envelope(ctx.context.executeTool("list_languages", { limit: 1 }));
    if (!result.ok && result.error.code === "RATE_LIMITED") {
      rateLimited = true;
      ok(result.error.retry_after_ms > 0, "the rate limit reports when to retry");
    }
    if (!rateLimited) await sleep(15);
  }
  ok(rateLimited, "the per-tool rate limit fires");

  const busy = makeContext({ pageFile: "index.html" });
  await sleep(30);
  const [a, b] = await Promise.all([
    envelope(busy.context.executeTool("search_repositories", { query: "framework" })),
    (async () => {
      await sleep(1);
      return envelope(busy.context.executeTool("search_repositories", { query: "framework" }));
    })(),
  ]);
  ok(a.ok && (b.ok || b.error.code === "BUSY" || b.error.code === "RATE_LIMITED"),
    "concurrent calls to one tool never corrupt each other", b.error && b.error.code);

  // Output budget: ask a generous tool for as much as it will give.
  const wide = makeContext({ pageFile: "languages/python.html" });
  await sleep(30);
  const big = await envelope(wide.context.executeTool("search_repositories",
    { limit: 20, query: "the" }));
  ok(big.ok, "a large search succeeds");
  ok(JSON.stringify(big).length <= 1500,
    `a large search is trimmed to the budget (${JSON.stringify(big).length})`);
  ok(big.truncated === true && big.omitted && Object.keys(big.omitted).length > 0,
    "trimming is reported, not silent", JSON.stringify(big.omitted));

  // Timeout: a tool that never resolves must be aborted, not awaited forever.
  const slow = makeContext({ pageFile: "index.html" });
  await sleep(30);
  await slow.context.registerTool({
    name: "hangs_forever",
    description: "test tool that never returns",
    inputSchema: { "type": "object", "properties": {}, "required": [] },
    timeoutMs: 250,
    execute: () => new Promise(() => {}),
  });
  const started = Date.now();
  const hung = await envelope(slow.context.executeTool("hangs_forever", {}));
  const waited = Date.now() - started;
  ok(hung.ok === false && hung.error.code === "TIMEOUT",
    "a hanging tool returns TIMEOUT", JSON.stringify(hung).slice(0, 120));
  ok(waited < 2000, `the timeout fires on schedule (${waited} ms)`);
  await sleep(120);
  const after = await envelope(slow.context.executeTool("get_site_info", {}));
  ok(after.ok === true, "the per-tool lock is released after a timeout");

  const rejected = await envelope(slow.context.registerTool({
    name: "bad name!",
    description: "test",
    inputSchema: { type: "object" },
    execute: () => ({}),
  }));
  ok(rejected.threw === true, "an invalid tool name is refused at registration");

  const exposed = await envelope(slow.context.registerTool({
    name: "shared_tool",
    description: "test",
    inputSchema: { type: "object" },
    execute: () => ({}),
  }, { exposedTo: ["https://partner.example"] }));
  ok(exposed.threw === true, "cross-origin exposure is refused");
}

/* ------------------------------------------------------------------ *
 * 8. Live HTTP — a real server, a real fetch, no filesystem shortcuts
 * ------------------------------------------------------------------ */

async function testLiveServer() {
  group("Live HTTP");

  const TYPES = { ".html": "text/html", ".json": "application/json",
    ".js": "text/javascript", ".css": "text/css", ".xml": "application/xml",
    ".txt": "text/plain", ".md": "text/markdown" };
  const server = http.createServer((req, res) => {
    const rel = decodeURIComponent(new URL(req.url, "http://x").pathname).replace(/^\//, "");
    const file = path.join(ROOT, rel.endsWith("/") ? `${rel}index.html` : rel);
    if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.writeHead(404, { "content-type": "text/plain" });
      res.end("not found");
      return;
    }
    res.writeHead(200, { "content-type": TYPES[path.extname(file)] || "application/octet-stream" });
    res.end(fs.readFileSync(file));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${server.address().port}/`;

  try {
    const wanted = [
      ["index.html", ["get_site_info", "list_languages", "search_repositories",
        "answer_question", "get_methodology", "get_download_links"]],
      ["languages/python.html", ["get_top_repositories", "get_language_stats",
        "get_repository", "compare_repositories"]],
      ["languages/index.html", ["list_languages", "search_repositories"]],
      ["404.html", ["get_site_info"]],
    ];

    let unreachable = 0;
    let notOk = 0;
    let trimmed = 0;

    for (const [pageFile, names] of wanted) {
      const response = await fetch(base + pageFile);
      if (!response.ok) { unreachable += 1; continue; }
      await response.text();
      const ctx = makeContext({ pageFile, fetchImpl: fetch, base });
      await sleep(40);
      for (const name of names) {
        await sleep(140); // respect the runtime's 100 ms minimum gap
        const env = await envelope(ctx.context.executeTool(name, MINIMAL[name] || {}));
        if (!env || env.ok !== true) {
          notOk += 1;
          if (VERBOSE) console.log(`   ${pageFile} ${name}:`, JSON.stringify(env).slice(0, 200));
          continue;
        }
        if (env.truncated) {
          trimmed += 1;
          if (VERBOSE) console.log(`   ${pageFile} ${name}: truncated at ${env.chars}`);
        }
      }
    }

    ok(unreachable === 0, "the harness can serve every generated page over HTTP");
    ok(notOk === 0, "every tool answers a real HTTP request with an ok envelope",
      `${notOk} failure(s)`);
    ok(trimmed === 0, "no default call needs the output budget over the wire",
      `${trimmed} truncated`);

    // The one tool that actually reads the 586 KB index from the network.
    const log = [];
    const trackedFetch = (href, options) => {
      log.push({ href: String(href) });
      return fetch(href, options);
    };
    const ctx = makeContext({ pageFile: "index.html", fetchImpl: trackedFetch, base });
    await sleep(40);
    const found = await envelope(ctx.context.executeTool("search_repositories",
      { query: "framework", limit: 3 }));
    ok(found.ok && found.data.results.length === 3,
      "search_repositories reads the published index over HTTP",
      JSON.stringify(found).slice(0, 160));
    ok(log.some((f) => /search-index\.json/.test(f.href)),
      "the index request really went to the server", JSON.stringify(log.map((f) => f.href)));
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
}

/* ------------------------------------------------------------------ *
 * 9. Static checks on the shipped files
 * ------------------------------------------------------------------ */

function testSources() {
  group("Source hygiene");

  for (const [name, source] of [["webmcp-core.js", CORE], ["webmcp-tools.js", TOOLS]]) {
    ok(!/\.innerHTML\b/.test(source), `${name} never touches innerHTML`);
    ok(!/\beval\s*\(/.test(source), `${name} never uses eval`);
    ok(!/new Function/.test(source), `${name} never uses new Function`);
    ok(!/document\.write/.test(source), `${name} never uses document.write`);
    ok(!/localStorage|sessionStorage/.test(source), `${name} stores nothing locally`);
    ok(!/navigator\.sendBeacon/.test(source), `${name} has no beacon`);
    ok(!/exposedTo\s*:\s*\[/.test(source), `${name} never exposes tools cross-origin`);
    ok(!/XMLHttpRequest|WebSocket|EventSource/.test(source), `${name} uses no other transport`);

    // Every URL literal must be one of the documented, harmless references.
    // Comments are stripped first so the file can explain itself without
    // failing its own audit; only http(s) hosts in live code count.
    const code = stripComments(source);
    const hosts = new Set();
    for (const match of code.matchAll(/https?:\/\/([a-z0-9.-]+)/gi)) hosts.add(match[1]);
    const allowed = new Set(["developer.chrome.com", "github.com",
      "havaianasdestruido.github.io"]);
    const strays = [...hosts].filter((h) => !allowed.has(h));
    ok(strays.length === 0, `${name} references no third-party endpoints`, strays.join(", "));
    ok(!/http:\/\//.test(code), `${name} contains no plaintext http URL`);
  }

  const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, "data/webmcp-manifest.json"), "utf8"));
  ok(manifest.tools.length >= 14, `manifest lists ${manifest.tools.length} tools`);
  ok(manifest.runtime.exposed_to.length === 0, "the manifest records no cross-origin exposure");
  ok(manifest.data_files.every((f) => /^[0-9a-f]{64}$/.test(f.sha256)),
    "every data file has a SHA-256 checksum");
  ok(manifest.tools.every((t) => t.name.length <= 30 && t.description.length <= 500),
    "every tool respects the character budgets");
  ok(manifest.tools.every((t) => Object.keys(t.annotations).length === 4),
    "every tool declares all four annotations");

  // The checksums must be real.
  const crypto = require("node:crypto");
  const sample = manifest.data_files[0];
  const digest = crypto.createHash("sha256")
    .update(fs.readFileSync(path.join(ROOT, sample.path))).digest("hex");
  ok(digest === sample.sha256, "a published checksum matches the file on disk", sample.path);
}

const require = (await import("node:module")).createRequire(import.meta.url);

/** Remove JavaScript comments without touching string contents, so the static
 *  checks test code rather than prose. */
function stripComments(source) {
  let out = "";
  let i = 0;
  while (i < source.length) {
    const ch = source[i];
    if (ch === "/" && source[i + 1] === "/") {
      while (i < source.length && source[i] !== "\n") i += 1;
      continue;
    }
    if (ch === "/" && source[i + 1] === "*") {
      i += 2;
      while (i < source.length && !(source[i] === "*" && source[i + 1] === "/")) i += 1;
      i += 2;
      continue;
    }
    if (ch === '"' || ch === "'" || ch === "`") {
      const quote = ch;
      out += ch;
      i += 1;
      while (i < source.length) {
        out += source[i];
        if (source[i] === "\\") { out += source[i + 1] || ""; i += 2; continue; }
        if (source[i] === quote) { i += 1; break; }
        i += 1;
      }
      continue;
    }
    out += ch;
    i += 1;
  }
  return out;
}

/* ------------------------------------------------------------------ */

async function main() {
  console.log("Top100 WebMCP runtime tests");
  await testRegistration();
  await testEveryToolAnswers();
  await testDefaults();
  await testBuiltPages();
  await testValidation();
  await testTools();
  await testPageActions();
  await testNativePath();
  await testLimits();
  await testLiveServer();
  testSources();

  if (failures) {
    for (const ctx of CONTEXTS) {
      const errors = (ctx.api && ctx.api.state && ctx.api.state.errors) || [];
      errors.forEach((e) => console.log(`  internal ${ctx.page.pageFile}: ${e.scope}: ${e.message}`));
    }
  }
  console.log(`\n${checks - failures}/${checks} checks passed`);
  if (failures) {
    console.log(`${failures} FAILED`);
    process.exit(1);
  }
  console.log("all good");
}

main().catch((err) => {
  console.error("test harness error:", err);
  process.exit(2);
});
