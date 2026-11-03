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
from pcat import provenance, search
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
            "requires (keep its structure, checks and library). Keep the '# pcat: <id>@v<N>' "
            "comment above each pattern function: it records where the code came from. If "
            "nothing fits, write the code normally. After writing code from a pattern, call "
            "check_code with your final code and the pattern id: it lists deviations from the "
            "reviewed pattern by severity. Fix every high-severity deviation unless the request "
            "explicitly requires it; in that case you may propose an approval: add a "
            "'# pcat-allow: <code> #<hash> -- <reason>' line above the function's marker, using "
            "the hash check_code shows. A proposal approves nothing until a human confirms it in "
            "the pull request, so say in your reply that a human needs to confirm it."
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
        marker = provenance.marker_line(meta.id, meta.version)
        public = {analysis.name_map[k] for k in analysis.name_map if k[0] == "f" and "." not in k
                  and (k == "f0" or analysis.name_map[k] in meta.exports)}
        public_placeholders = sorted(k for k, v in analysis.name_map.items()
                                     if "." not in k and k[0] == "f" and v in public)
        code = provenance.add_markers(code, marker, [mapping[k] for k in public_placeholders])
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
            "marker": marker,
            "names": {k: v for k, v in analysis.name_map.items()},
        }
        if meta.status == "deprecated":
            result["warning"] = (
                f"{meta.key} is deprecated; use {meta.replaced_by} instead"
            )
        self._log("get_pattern", {"id": id, "names": names},
                  {"id": meta.key, "status": meta.status})
        return result

    def check_code(self, code: str, pattern_id: str | None = None) -> dict[str, Any]:
        arguments: dict[str, Any] = {"length": len(code)}
        if pattern_id is not None:
            arguments["pattern_id"] = pattern_id
        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError) as exc:
            line = getattr(exc, "lineno", None)
            message = f"syntax error{f' at line {line}' if line else ''}: {getattr(exc, 'msg', exc)}"
            self._log("check_code", arguments, {"error": "syntax"})
            return {"error": message, "functions": []}
        pattern = None
        if pattern_id is not None:
            try:
                pattern = cat.get_one(self.root, pattern_id)
            except PcatError:
                known = ", ".join(sorted({p.meta.id for p in self._patterns.values()}))
                self._log("check_code", arguments, {"error": "unknown id"})
                raise PcatError(f"unknown pattern id {pattern_id!r}; known ids: {known}") from None
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
        result: dict[str, Any] = {
            "functions": functions, "summary": summary,
            "legend": {"covered": "matches a reviewed pattern exactly (names aside)",
                       "near": "same structure as a reviewed pattern; only literal values differ",
                       "none": "no reviewed pattern"},
        }
        result.update(self._provenance_and_deviations(code, tree, functions, pattern))
        self._log("check_code", arguments, {
            "statuses": [(f["name"], f["status"], f["pattern"]) for f in functions],
            "deviations": [(a["function"], a["pattern"], [(d["code"], d["approved"]) for d in a["deviations"]])
                           for a in result["deviations"]],
        })
        return result

    def _provenance_and_deviations(self, code: str, tree: ast.Module, functions: list[dict],
                                   pattern) -> dict[str, Any]:
        """v4: markers, advisory inferred provenance and deviations from the source pattern."""
        from pcat import deviation, lint

        infos = provenance.functions(code, tree)
        by_line = {i.node.lineno: i for i in infos}
        catalog = self._lint_catalog()
        problems: list[str] = []
        targets: list[tuple] = []
        for info in infos:
            if info.marker is None:
                continue
            marked = catalog.resolve(info.marker)
            if marked is None:
                problems.append(f"line {info.marker.line}: unknown pattern {info.marker.ref} in marker")
            else:
                targets.append((info, marked, None, "marker"))
        if pattern is not None:
            refs = [r for r in catalog.refs if r.pattern_id == pattern.meta.id]
            taken = {id(t[0].node) for t in targets if t[1].meta.id == pattern.meta.id}
            pairs = []
            for ref in refs:
                for info in infos:
                    text = provenance.shape_text(info.node)
                    if text is not None and id(info.node) not in taken:
                        pairs.append((provenance.variance.similarity(text, ref.shape_text), info.qualname,
                                      ref.function, info))
            pairs.sort(key=lambda p: (-p[0], p[1], p[2]))
            used_f = {t[0].qualname for t in targets}
            used_r = {deviation.choose_pattern_function(t[0].node, t[1]) for t in targets
                      if t[1].meta.id == pattern.meta.id}
            for sim, qualname, function, info in pairs:
                if qualname in used_f or function in used_r:
                    continue
                if function != pattern.meta.entry_point and sim < provenance.INFERENCE_THRESHOLD:
                    continue  # an export the code does not seem to contain
                used_f.add(qualname)
                used_r.add(function)
                targets.append((info, pattern, function, "pattern_id"))
        analyses = []
        for info, pat, function, source in sorted(targets, key=lambda t: (t[0].node.lineno, t[0].qualname)):
            a = deviation.analyze_function(tree, info.node, pat, function)
            current_hash = provenance.function_hash(info.node)
            # Agent context: an approval written in the code is only a proposal (base_keys empty).
            devs, stale, _, _ = lint.apply_approvals(info, a.deviations, "<code>",
                                                     current_hash=current_hash, base_keys=set())
            analyses.append({
                "function": info.qualname, "line": info.node.lineno, "pattern": pat.meta.key,
                "pattern_function": a.pattern_function, "provenance": source, "hash": current_hash,
                "approval_template": provenance.approval_line("<code>", current_hash),
                "deviations": devs, "stale_approvals": stale,
                "invalid_approvals": [{"line": x.line, "problem": x.problem} for x in info.approvals if x.problem],
                "diff": a.diff,
            })
        refs = catalog.refs
        for item in functions:
            info = by_line.get(item["line"])
            item["marker"] = info.marker.ref if info is not None and info.marker else None
            inf = provenance.infer(info.node, refs) if info is not None else None
            item["inferred"] = None if inf is None else {
                "pattern": f"{inf.pattern_id}@v{inf.version}", "pattern_function": inf.function,
                "similarity": inf.similarity, "likely_derived": inf.derived}
        high = sum(1 for a in analyses for d in a["deviations"]
                   if d["severity"] == "high" and not d["approved"] and d["approval_state"] != "proposed")
        proposed = sum(1 for a in analyses for d in a["deviations"] if d["approval_state"] == "proposed")
        out: dict[str, Any] = {"deviations": analyses, "unapproved_high": high,
                               "awaiting_human_confirmation": proposed}
        if problems:
            out["problems"] = problems
        if not analyses:
            out["next_step"] = ("No marked functions: pass pattern_id (the pattern you used) to see "
                                "deviations from it.")
        elif high:
            out["next_step"] = (
                "Fix every high-severity deviation unless the request explicitly requires it; for "
                "one the request requires, propose an approval by adding '# pcat-allow: <code> "
                "#<hash> -- <reason>' (the function's hash is shown with each deviation) directly "
                "above the function's marker, and tell the user a human must confirm it.")
        elif proposed:
            out["next_step"] = (
                "Proposed approvals are not approvals until a human confirms them in the pull "
                "request: say so in your reply.")
        else:
            out["next_step"] = "No unapproved high-severity deviations."
        return out

    def _lint_catalog(self):
        from pcat import lint

        if getattr(self, "_catalog", None) is None:
            self._catalog = lint.Catalog(self.root)
        return self._catalog

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
