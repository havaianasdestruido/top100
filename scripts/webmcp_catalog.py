#!/usr/bin/env python3
"""
Read the WebMCP tool catalogue out of assets/webmcp-tools.js.

The tool definitions are the single source of truth: they live in the browser
script that actually registers them. This module parses them back out of the
JavaScript (strictly, with a real scanner rather than a regex) so that the
machine-readable manifest, the documentation page and the tests are all built
from the same definitions and cannot drift.

Only two shapes are understood, and both are enforced by the tests:

    define({
      name: "tool_name",                       // double-quoted string literal
      description: "one line, <= 500 chars",   // double-quoted string literal
      inputSchema: { ...strict JSON... },
      annotations: { ...strict JSON... },
      pages: ["all"],
      timeoutMs: 15000,                        // optional
      execute: function (args) { ... }
    });

Anything else raises CatalogueError, so a malformed tool breaks the build
instead of silently disappearing from the docs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

TOOLS_JS = Path(__file__).resolve().parent.parent / "assets" / "webmcp-tools.js"

# Character budgets from Chrome's WebMCP tool-security guidance.
BUDGET = {
    "name": 30,
    "description": 500,
    "parameter_name": 30,
    "parameter_description": 150,
    "output": 1500,
}

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,%d}$" % (BUDGET["name"] - 1))
PAGES = {"all", "home", "languages", "language", "methodology", "dataset",
         "compare", "faq", "404", "webmcp", "repos", "table"}
ANNOTATION_KEYS = ("readOnlyHint", "untrustedContentHint", "consequentialHint", "debugging")


class CatalogueError(RuntimeError):
    """The tool catalogue could not be read or does not satisfy the rules."""


# ---------------------------------------------------------------------------
# A small scanner for JavaScript object literals
# ---------------------------------------------------------------------------

def _skip_ws(text: str, i: int) -> int:
    while i < len(text):
        ch = text[i]
        if ch in " \t\r\n":
            i += 1
        elif text.startswith("//", i):
            nl = text.find("\n", i)
            i = len(text) if nl == -1 else nl + 1
        elif text.startswith("/*", i):
            end = text.find("*/", i)
            i = len(text) if end == -1 else end + 2
        else:
            break
    return i


def _scan_string(text: str, i: int) -> int:
    """Return the index just past the string literal starting at i."""
    quote = text[i]
    i += 1
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == quote:
            return i + 1
        i += 1
    raise CatalogueError("unterminated string literal in webmcp-tools.js")


def _scan_value(text: str, i: int):
    """Scan one value starting at i; return (start, end) with end exclusive.

    String literals may be concatenated with `+`, which is how long, readable
    tool descriptions are written."""
    start = i
    ch = text[i]
    if ch in "\"'`":
        end = _scan_string(text, i)
        while True:
            after = _skip_ws(text, end)
            if after < len(text) and text[after] == "+":
                after = _skip_ws(text, after + 1)
                if after < len(text) and text[after] in "\"'`":
                    end = _scan_string(text, after)
                    continue
            return start, end
    if ch in "{[":
        close = "}" if ch == "{" else "]"
        depth = 0
        while i < len(text):
            c = text[i]
            if c in "\"'`":
                i = _scan_string(text, i)
                continue
            if c == "/" and i + 1 < len(text) and text[i + 1] in "/*":
                i = _skip_ws(text, i)
                continue
            if c == close:
                depth -= 1
                if depth == 0:
                    return start, i + 1
                i += 1
                continue
            if c == ch:
                depth += 1
            i += 1
        raise CatalogueError("unbalanced %s in webmcp-tools.js" % ch)
    # A scalar — or a function expression, whose body is brace-scanned so that
    # the commas and braces inside it do not end the value early.
    j = i
    while j < len(text) and text[j] not in ",}\n":
        if text[j] == "{":
            _, end = _scan_value(text, j)
            return start, end
        if text[j] in "\"'`":
            j = _scan_string(text, j)
            continue
        j += 1
    return start, j


def _top_level_fields(body: str) -> dict:
    """Split an object literal body into {key: raw value text} at depth 1."""
    fields: dict = {}
    i = 0
    while True:
        i = _skip_ws(body, i)
        if i >= len(body):
            return fields
        match = re.match(r"([A-Za-z_$][A-Za-z0-9_$]*)\s*:", body[i:])
        if not match:
            raise CatalogueError("expected `key:` at offset %d in a tool definition" % i)
        key = match.group(1)
        if key in fields:
            raise CatalogueError("duplicate field %r in a tool definition" % key)
        i += match.end()
        i = _skip_ws(body, i)
        start, end = _scan_value(body, i)
        fields[key] = body[start:end].strip()
        i = end
        i = _skip_ws(body, i)
        if i < len(body) and body[i] == ",":
            i += 1
            continue
        if i >= len(body):
            return fields


def _collect_constants(text: str) -> dict:
    """Resolve the shared `var NAME = {...}` literals at the top of the file, so
    tools can reuse common annotation sets without the catalogue turning into a
    copy-paste of the same object 15 times."""
    constants = {}
    for match in re.finditer(r"\bvar\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*([{\[])", text):
        start, end = _scan_value(text, match.start(2))
        raw = text[start:end]
        try:
            constants[match.group(1)] = json.loads(re.sub(r",(\s*[}\]])", r"\1", raw))
        except json.JSONDecodeError:
            continue
    return constants


def _json_literal(raw: str, what: str, name: str, constants=None):
    """Parse a raw slice as JSON, tolerating the trailing commas JS allows and
    resolving references to shared constant literals."""
    stripped = raw.strip()
    if constants and re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", stripped):
        if stripped not in constants:
            raise CatalogueError("%s of tool %r references an unknown constant %r"
                                 % (what, name, stripped))
        return constants[stripped]
    text = re.sub(r",(\s*[}\]])", r"\1", stripped)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise CatalogueError("%s of tool %r is not a JSON literal: %s" % (what, name, exc))


def _js_string(raw: str, what: str, name: str) -> str:
    """Read a value that must be a double-quoted string literal, or several of
    them joined with `+` (the style used for readable multi-line descriptions).

    Nothing else is accepted: no template literals, no variables, no calls."""
    parts = []
    i = 0
    length = len(raw)
    while True:
        i = _skip_ws(raw, i)
        if i >= length:
            break
        if raw[i] != '"':
            raise CatalogueError("%s of tool %r must be a double-quoted string literal "
                                 "(found %r)" % (what, name, raw[i:i + 12]))
        end = _scan_string(raw, i)
        try:
            parts.append(json.loads(raw[i:end]))
        except json.JSONDecodeError as exc:
            raise CatalogueError("%s of tool %r has an unreadable string literal: %s"
                                 % (what, name, exc))
        i = _skip_ws(raw, end)
        if i >= length:
            break
        if raw[i] != "+":
            raise CatalogueError("%s of tool %r must be string literals joined by `+` "
                                 "(found %r)" % (what, name, raw[i:i + 12]))
        i += 1
    if not parts:
        raise CatalogueError("%s of tool %r is empty" % (what, name))
    return "".join(parts)


def parse_tools(path: Path = TOOLS_JS):
    """Return the list of tool definitions, in source order."""
    text = Path(path).read_text(encoding="utf-8")
    constants = _collect_constants(text)
    tools = []
    for match in re.finditer(r"\bdefine\(\s*\{", text):
        open_brace = text.index("{", match.start())
        start, end = _scan_value(text, open_brace)
        body = text[start + 1:end - 1]
        fields = _top_level_fields(body)

        missing = [k for k in ("name", "description", "inputSchema", "annotations", "pages")
                   if k not in fields]
        if missing:
            raise CatalogueError("tool at offset %d is missing %s"
                                 % (match.start(), ", ".join(missing)))

        name = _js_string(fields["name"], "name", fields["name"][:40])
        tool = {
            "name": name,
            "description": _js_string(fields["description"], "description", name),
            "inputSchema": _json_literal(fields["inputSchema"], "inputSchema", name, constants),
            "annotations": _json_literal(fields["annotations"], "annotations", name, constants),
            "pages": _json_literal(fields["pages"], "pages", name, constants),
            "timeoutMs": None,
            "source_offset": match.start(),
        }
        if "timeoutMs" in fields:
            tool["timeoutMs"] = int(str(fields["timeoutMs"]).strip())
        tools.append(tool)

    if not tools:
        raise CatalogueError("no tool definitions found in %s" % path)
    return tools


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_tools(tools) -> list:
    """Return a list of human-readable problems; empty means the catalogue is good."""
    problems = []
    seen = set()

    if len(tools) > 24:
        problems.append("more than 24 tools are defined (%d)" % len(tools))

    for tool in tools:
        name = tool["name"]
        where = "tool %r" % name

        if not NAME_RE.match(name):
            problems.append("%s: name must be lower_snake_case, start with a letter "
                            "and be at most %d characters" % (where, BUDGET["name"]))
        if name in seen:
            problems.append("%s: duplicate tool name" % where)
        seen.add(name)

        desc = tool["description"]
        if not desc.strip():
            problems.append("%s: description is empty" % where)
        if len(desc) > BUDGET["description"]:
            problems.append("%s: description is %d characters (budget %d)"
                            % (where, len(desc), BUDGET["description"]))

        schema = tool["inputSchema"]
        if not isinstance(schema, dict) or schema.get("type") != "object":
            problems.append("%s: inputSchema must be a JSON object schema" % where)
            continue

        props = schema.get("properties", {})
        if not isinstance(props, dict):
            problems.append("%s: inputSchema.properties must be an object" % where)
            props = {}
        for param, spec in props.items():
            if len(param) > BUDGET["parameter_name"]:
                problems.append("%s: parameter %r is longer than %d characters"
                                % (where, param, BUDGET["parameter_name"]))
            if not isinstance(spec, dict):
                problems.append("%s: parameter %r has no schema" % (where, param))
                continue
            pdesc = spec.get("description", "")
            if not pdesc:
                problems.append("%s: parameter %r has no description" % (where, param))
            elif len(pdesc) > BUDGET["parameter_description"]:
                problems.append("%s: parameter %r description is %d characters (budget %d)"
                                % (where, param, len(pdesc), BUDGET["parameter_description"]))
            ptype = spec.get("type")
            if ptype not in ("string", "integer", "number", "boolean", "array", "object"):
                problems.append("%s: parameter %r has type %r" % (where, param, ptype))
            if ptype in ("integer", "number"):
                if "maximum" not in spec or "minimum" not in spec:
                    problems.append("%s: numeric parameter %r needs minimum and maximum bounds"
                                    % (where, param))
            if ptype == "array":
                if "maxItems" not in spec:
                    problems.append("%s: array parameter %r needs maxItems" % (where, param))
                if not isinstance(spec.get("items"), dict):
                    problems.append("%s: array parameter %r needs an items schema"
                                    % (where, param))
            if ptype == "string" and "enum" not in spec and "maxLength" not in spec:
                problems.append("%s: string parameter %r needs maxLength or enum"
                                % (where, param))

        required = schema.get("required", [])
        if not isinstance(required, list):
            problems.append("%s: inputSchema.required must be an array" % where)
        else:
            for key in required:
                if key not in props:
                    problems.append("%s: required parameter %r is not defined" % (where, key))

        annotations = tool["annotations"]
        if not isinstance(annotations, dict):
            problems.append("%s: annotations must be an object" % where)
        else:
            for key in ANNOTATION_KEYS:
                if key not in annotations:
                    problems.append("%s: annotation %r is missing" % (where, key))
            if annotations.get("consequentialHint"):
                problems.append("%s: this site has no consequential tools; "
                                "consequentialHint must stay false" % where)
            for key in annotations:
                if key not in ANNOTATION_KEYS:
                    problems.append("%s: unknown annotation %r" % (where, key))

        pages = tool["pages"]
        if not isinstance(pages, list) or not pages:
            problems.append("%s: pages must be a non-empty array" % where)
        else:
            for page in pages:
                if page not in PAGES:
                    problems.append("%s: unknown page scope %r" % (where, page))

    return problems


def load_tools(path: Path = TOOLS_JS):
    """Parse and validate; raises CatalogueError on any problem."""
    tools = parse_tools(path)
    problems = validate_tools(tools)
    if problems:
        raise CatalogueError("; ".join(problems))
    return tools


if __name__ == "__main__":
    import sys
    try:
        loaded = load_tools()
    except CatalogueError as exc:
        print("catalogue error: %s" % exc, file=sys.stderr)
        sys.exit(1)
    for item in loaded:
        print("%-28s %-9s %3d chars  pages=%s"
              % (item["name"], "read" if item["annotations"]["readOnlyHint"] else "act",
                 len(item["description"]), ",".join(item["pages"])))
    print("\n%d tools" % len(loaded))
