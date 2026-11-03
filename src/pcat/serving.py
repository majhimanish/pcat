"""Catalog tools served to coding agents (v3). No dependency on the MCP SDK.

`CatalogService` implements the three tools that `pcat serve` exposes over MCP:
search_patterns, get_pattern and check_code. Every result is a JSON-serializable
dict, deterministic for the same catalog and arguments. Errors are raised as
PcatError with a message meant for the agent.
"""

from __future__ import annotations

import ast
import datetime as dt
import json
from pathlib import Path
from typing import Any

from pcat import canonical, miner
from pcat import catalog as cat
from pcat import search
from pcat.errors import PcatError

NO_MATCH_MESSAGE = (
    "No reviewed pattern fits this request. Write the code normally; do not force a "
    "catalog pattern onto it."
)
MATCH_MESSAGE = (
    "Reviewed patterns found. If one fits, call get_pattern with its id and use that "
    "code, adapting only names and what the request explicitly requires."
)


class CatalogService:
    def __init__(self, root: Path, log_path: Path | None = None):
        self.root = Path(root)
        self.log_path = Path(log_path) if log_path else None
        self.index = search.SearchIndex.from_root(self.root)
        self._patterns = {p.meta.key: p for p in cat.load_catalog(self.root) if p.meta}
        self._function_fps = self._catalog_function_fingerprints()

    # ------------------------------------------------------------------ #
    # Instructions
    # ------------------------------------------------------------------ #

    def instructions(self) -> str:
        by_category: dict[str, list[str]] = {}
        for entry in self.index.entries:  # active patterns, sorted by id
            by_category.setdefault(entry["category"], []).append(entry["title"])
        topics = "; ".join(
            f"{category}: {', '.join(titles)}" for category, titles in sorted(by_category.items())
        )
        return (
            "This organization keeps reviewed, tested code patterns. Before writing code for a "
            "common application task, call search_patterns with a short description of what "
            f"you need. The catalog currently covers: {topics}. If a pattern fits, call "
            "get_pattern and use its code, adapting only names and what the request explicitly "
            "requires (keep its structure, checks and library). If nothing fits, write the code "
            "normally. Afterwards, call check_code on your final code to confirm which "
            "functions match a reviewed pattern."
        )

    # ------------------------------------------------------------------ #
    # Tools
    # ------------------------------------------------------------------ #

    def search_patterns(self, request: str, limit: int = 5) -> dict[str, Any]:
        if not isinstance(request, str) or not request.strip():
            raise PcatError("request must be a non-empty description of the code you need")
        limit = max(1, min(int(limit), 20))
        hits = self.index.search(request, limit=limit)
        matches = [
            {
                "id": h.id,
                "version": h.version,
                "title": h.entry["title"],
                "summary": h.entry["summary"],
                "use_when": h.entry.get("use_when"),
                "score": round(h.score, 3),
                "requires": h.entry.get("requires") or [],
                "exports": h.entry.get("exports") or [],
            }
            for h in hits
        ]
        result = {"matches": matches, "message": MATCH_MESSAGE if matches else NO_MATCH_MESSAGE}
        self._log("search_patterns", {"request": request, "limit": limit},
                  {"ids": [m["id"] for m in matches], "scores": [m["score"] for m in matches]})
        return result

    def get_pattern(self, id: str, names: dict[str, str] | None = None) -> dict[str, Any]:
        try:
            pattern = cat.get_one(self.root, id)
        except PcatError:
            known = ", ".join(sorted({p.meta.id for p in self._patterns.values()}))
            self._log("get_pattern", {"id": id, "names": names}, {"error": "unknown id"})
            raise PcatError(f"unknown pattern id {id!r}; known ids: {known}") from None
        meta = pattern.meta
        analysis = cat.analyze_pattern(pattern)
        mapping = dict(analysis.name_map)
        if names:
            unknown = sorted(set(names) - set(mapping))
            if unknown:
                self._log("get_pattern", {"id": id, "names": names}, {"error": "invalid names"})
                raise PcatError(
                    f"invalid name keys {unknown}; valid keys for {meta.key}: "
                    + ", ".join(f"{k} ({v})" for k, v in mapping.items())
                )
            mapping.update(names)
        code = canonical.render(analysis.text, mapping)
        try:
            same = canonical.canonicalize(code, mapping["f0"], meta.keep_annotations) == analysis.text
        except PcatError:
            same = False
        if not same:
            raise PcatError("these names make two names collide; choose different names")
        result: dict[str, Any] = {
            "id": meta.id,
            "version": meta.version,
            "status": meta.status,
            "title": meta.title,
            "summary": meta.summary,
            "entry_point": mapping["f0"],
            "exports": meta.exports,
            "requires": meta.requires,
            "usage": meta.usage,
            "code": code,
            "names": {k: v for k, v in analysis.name_map.items()},
        }
        if meta.status == "deprecated":
            result["warning"] = (
                f"{meta.key} is deprecated; use {meta.replaced_by} instead"
            )
        self._log("get_pattern", {"id": id, "names": names},
                  {"id": meta.key, "status": meta.status})
        return result

    def check_code(self, code: str) -> dict[str, Any]:
        try:
            ast.parse(code)
        except (SyntaxError, ValueError) as exc:
            line = getattr(exc, "lineno", None)
            message = f"syntax error{f' at line {line}' if line else ''}: {getattr(exc, 'msg', exc)}"
            self._log("check_code", {"length": len(code)}, {"error": "syntax"})
            return {"error": message, "functions": []}
        analysis = miner.analyze_source(code.encode("utf-8"), miner.MineSettings(fragments=False))
        functions = []
        for f in analysis["functions"]:
            item: dict[str, Any] = {"name": f["qualname"], "line": f["lineno"], "status": "none",
                                    "pattern": None, "pattern_function": None}
            if f["error"] is None:
                exact = self._function_fps["exact"].get(f["exact_fingerprint"])
                near = self._function_fps["shape"].get(f["shape_fingerprint"])
                if exact:
                    item.update(status="covered", pattern=exact[0], pattern_function=exact[1])
                elif near:
                    item.update(status="near", pattern=near[0], pattern_function=near[1])
            else:
                item["note"] = f["error"]
            functions.append(item)
        summary = {s: sum(1 for f in functions if f["status"] == s) for s in ("covered", "near", "none")}
        self._log("check_code", {"length": len(code)},
                  {"statuses": [(f["name"], f["status"], f["pattern"]) for f in functions]})
        return {"functions": functions, "summary": summary,
                "legend": {"covered": "matches a reviewed pattern exactly (names aside)",
                           "near": "same structure as a reviewed pattern; only literal values differ",
                           "none": "no reviewed pattern"}}

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _catalog_function_fingerprints(self) -> dict[str, dict[str, tuple[str, str]]]:
        """Exact/shape fingerprint -> (pattern key, function) for entry points and exports."""
        exact: dict[str, tuple[str, str]] = {}
        shape: dict[str, tuple[str, str]] = {}
        for key in sorted(self._patterns):
            pattern = self._patterns[key]
            if pattern.meta.status != "active":
                continue
            tree = ast.parse(pattern.impl_path.read_text(encoding="utf-8"))
            wanted = [pattern.meta.entry_point, *pattern.meta.exports]
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted:
                    mined = miner.mine_function(node)
                    exact.setdefault(mined["exact_fingerprint"], (pattern.meta.id, node.name))
                    shape.setdefault(mined["shape_fingerprint"], (pattern.meta.id, node.name))
        return {"exact": exact, "shape": shape}

    def _log(self, tool: str, arguments: dict, summary: dict) -> None:
        if not self.log_path:
            return
        line = {
            "tool": tool,
            "arguments": arguments,
            "result": summary,
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds"),
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, sort_keys=True, default=str) + "\n")
