"""v5 simulation logic: tasks from real app code, working copies, scoring helpers.

Driven by scripts/v5.py. Pure functions where possible; the `claude -p` runs live in
the script. Nothing here talks to the network.
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from pcat import provenance
from pcat.errors import PcatError

REQUEST_PROMPT = (
    "Here is a situation a software developer is in:\n\n{need}\n\n"
    "Write the request this developer would type to an AI coding assistant that is working "
    "inside their repository. Make it brief, the way developers actually type into an "
    "assistant: usually under 15 words, no greeting, no explanation. Reply with only the "
    "request text."
)
REPO_NOTE = "This repo uses the organization's pattern catalog via the pcat tools."
COPY_IGNORE = (".git", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv")


@dataclass(frozen=True)
class Task:
    app: str
    id: str
    kind: str  # pattern | negative
    file: str
    remove: tuple[str, ...]
    pattern: str | None
    relation: str | None
    need: str

    @property
    def entry(self) -> str:
        """The function the task is about (the last one listed; helpers come first)."""
        return self.remove[-1]


def load_tasks(path: Path) -> list[Task]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    out = []
    for app, tasks in sorted(data["apps"].items()):
        for tid, t in sorted(tasks.items()):
            if t["kind"] not in ("pattern", "negative"):
                raise PcatError(f"{tid}: kind must be pattern or negative")
            if (t["kind"] == "pattern") != bool(t.get("pattern")):
                raise PcatError(f"{tid}: pattern tasks need a pattern, negatives none")
            out.append(Task(app, tid, t["kind"], t["file"], tuple(t["remove"]), t.get("pattern"),
                            t.get("relation"), " ".join(t["need"].split())))
    return out


# --------------------------------------------------------------------------- #
# Removing functions
# --------------------------------------------------------------------------- #


def _spans(source: str, names: tuple[str, ...]) -> dict[str, tuple[int, int]]:
    """name -> (first line, last line), 1-based inclusive; the first line includes
    decorators and the comment block directly above."""
    tree = ast.parse(source)
    lines = source.splitlines()
    found: dict[str, list[tuple[int, int]]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            start = min([node.lineno, *(d.lineno for d in node.decorator_list)])
            block = provenance.comment_block(lines, start)
            if block:
                start = block[0][0]
            found.setdefault(node.name, []).append((start, node.end_lineno))
    for name in names:
        if name not in found:
            raise PcatError(f"no top-level function {name!r}")
        if len(found[name]) > 1:
            raise PcatError(f"function {name!r} is defined more than once")
    return {name: found[name][0] for name in names}


def remove_functions(source: str, names: tuple[str, ...]) -> tuple[str, dict[str, str]]:
    """Source without the named top-level functions, and each one's original text."""
    spans = _spans(source, names)
    lines = source.splitlines(keepends=True)
    refs = {name: "".join(lines[a - 1:b]) for name, (a, b) in spans.items()}
    drop: set[int] = set()
    for a, b in spans.values():
        drop.update(range(a, b + 1))
        n = b + 1  # also drop the blank lines that separated it from what follows
        while n <= len(lines) and not lines[n - 1].strip():
            drop.add(n)
            n += 1
    kept = [line for i, line in enumerate(lines, 1) if i not in drop]
    new = "".join(kept)
    if not new.endswith("\n"):
        new += "\n"
    ast.parse(new)  # still valid Python
    return new, refs


def reference_source(source: str, names: tuple[str, ...]) -> str:
    """The removed functions, in source order, separated by blank lines."""
    _, refs = remove_functions(source, names)
    spans = _spans(source, names)
    return "\n\n".join(refs[n].rstrip("\n") for n in sorted(names, key=lambda n: spans[n][0])) + "\n"


# --------------------------------------------------------------------------- #
# Working copies
# --------------------------------------------------------------------------- #


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-c", "user.name=pcat-v5", "-c", "user.email=v5@example.invalid", *args],
                          cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise PcatError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def prepare_workdir(app_dir: Path, dest: Path, task: Task, condition: str) -> dict:
    """Fresh copy of the app with the task's functions removed, committed as the baseline.

    condition "pcat" also adds the repo note to CLAUDE.md (created if absent) before the
    baseline commit, so neither change shows in the run's diff.
    """
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(app_dir, dest, ignore=shutil.ignore_patterns(*COPY_IGNORE), symlinks=True)
    target = dest / task.file
    new, _ = remove_functions(target.read_text(encoding="utf-8"), task.remove)
    target.write_text(new, encoding="utf-8")
    if condition == "pcat":
        note = dest / "CLAUDE.md"
        text = note.read_text(encoding="utf-8") if note.exists() else ""
        note.write_text(text + ("\n" if text and not text.endswith("\n") else "") + REPO_NOTE + "\n",
                        encoding="utf-8")
    _git(dest, "init", "-q")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-q", "--no-verify", "-m", "v5 task baseline")
    return {"baseline": _git(dest, "rev-parse", "HEAD").strip()}


def final_diff(dest: Path) -> tuple[str, list[str]]:
    """Unified diff of everything the run changed (tracked and new files) and the files touched."""
    _git(dest, "add", "-A")
    diff = _git(dest, "diff", "--cached", "--no-color", "--no-ext-diff")
    names = _git(dest, "diff", "--cached", "--name-only").split()
    return diff, sorted(names)


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #


def request_jobs(tasks: list[Task], extra: dict) -> list[dict]:
    """One request per task, plus the extra retrieval needs (`extra[app]` = list of
    {need, expected}). Ids are stable so generation can resume."""
    jobs = [{"id": t.id, "app": t.app, "kind": t.kind, "expected": t.pattern, "need": t.need,
             "set": "task"} for t in tasks]
    for app, items in sorted(extra.items()):
        for n, item in enumerate(items, 1):
            jobs.append({"id": f"{app}_extra_{n:02d}", "app": app,
                         "kind": "pattern" if item.get("expected") else "negative",
                         "expected": item.get("expected"), "need": " ".join(item["need"].split()),
                         "set": "extra"})
    for job in jobs:
        job["prompt"] = REQUEST_PROMPT.format(need=job["need"])
    return jobs


def word_count(text: str) -> int:
    return len(text.split())


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


@dataclass
class RunPaths:
    root: Path
    app: str
    task: str
    condition: str
    sample: int
    files: dict = field(default_factory=dict)

    @property
    def stem(self) -> Path:
        return self.root / self.app / self.task / self.condition / f"sample_{self.sample:02d}"


# --------------------------------------------------------------------------- #
# Retrieval (Part E)
# --------------------------------------------------------------------------- #


def overlap_summary(items: list[dict], house: set[str], threshold: float) -> dict:
    """Requests where a house and a generic pattern both pass the threshold: which ranks first.

    items: {expected, ranked: [(id, score), ...]}; `house` = ids of the app's own patterns.
    """
    rows = []
    for item in items:
        above = [(pid, s) for pid, s in item["ranked"] if s >= threshold]
        kinds = {("house" if pid in house else "generic") for pid, _ in above}
        if {"house", "generic"} <= kinds:
            first = above[0][0]
            rows.append({"request": item["request"], "expected": item["expected"], "first": first,
                         "first_kind": "house" if first in house else "generic",
                         "first_is_expected": first == item["expected"],
                         "above": [[pid, round(s, 3)] for pid, s in above[:4]]})
    return {
        "both_above_threshold": len(rows),
        "house_first": sum(r["first_kind"] == "house" for r in rows),
        "generic_first": sum(r["first_kind"] == "generic" for r in rows),
        "first_is_expected": sum(r["first_is_expected"] for r in rows),
        "rows": rows,
    }


def below_threshold(items: list[dict], threshold: float) -> dict:
    """Positives whose expected pattern ranks first but scores under the threshold (short queries)."""
    pos = [i for i in items if i["expected"]]
    under = [i for i in pos if i["ranked"] and i["ranked"][0][0] == i["expected"] and i["ranked"][0][1] < threshold]
    return {"positives": len(pos), "ranked_first_but_below_threshold": len(under),
            "examples": [{"request": i["request"], "score": round(i["ranked"][0][1], 3), "words": len(i["request"].split())}
                         for i in under]}


# --------------------------------------------------------------------------- #
# End-to-end runs (Part F)
# --------------------------------------------------------------------------- #

# File tools in full; the shell only through an allowlist of read-only commands. Unrestricted
# Bash for unattended agents was refused as unsafe in this environment (DECISIONS.md).
ALLOWED_TOOLS = (
    "Read", "Edit", "MultiEdit", "Write", "Glob", "Grep", "LS", "TodoWrite",
    "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git grep:*)", "Bash(git show:*)",
    "Bash(ls:*)", "Bash(head:*)", "Bash(wc:*)", "Bash(python -m py_compile:*)",
)
DISALLOWED_TOOLS = ("WebFetch", "WebSearch", "Agent", "Task", "NotebookEdit")
PCAT_TOOLS = ("mcp__pcat__search_patterns", "mcp__pcat__get_pattern", "mcp__pcat__check_code")
STRIPPED_ENV = ("CLAUDE_ADDITIONAL_DIRECTORIES", "CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD")


def run_command(request: str, model: str, mcp_config: Path | None) -> list[str]:
    """`claude -p` with full file and shell tools, no web or subagents, project settings only."""
    tools = [*ALLOWED_TOOLS, *(PCAT_TOOLS if mcp_config else ())]
    cmd = ["claude", "-p", request, "--output-format", "stream-json", "--verbose",
           "--no-session-persistence", "--strict-mcp-config", "--model", model,
           "--setting-sources", "project,local", "--disable-slash-commands",
           "--allowedTools", *tools,
           "--disallowedTools", *DISALLOWED_TOOLS]
    if mcp_config:
        cmd[3:3] = ["--mcp-config", str(mcp_config)]
    return cmd


def parse_stream(lines: list[str]) -> dict:
    """Summary of a stream-json transcript: tool calls in order, result, cost, turns."""
    calls, result = [], {}
    for raw in lines:
        try:
            event = json.loads(raw)
        except ValueError:
            continue
        if event.get("type") == "assistant":
            for block in (event.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    calls.append({"tool": block.get("name"), "input": block.get("input") or {}})
        elif event.get("type") == "result":
            result = event
    return {
        "tool_calls": calls,
        "result_text": result.get("result"),
        "is_error": bool(result.get("is_error")) if result else True,
        "cost_usd": result.get("total_cost_usd"),
        "duration_ms": result.get("duration_ms"),
        "num_turns": result.get("num_turns"),
        "finished": bool(result),
    }


def tool_order(calls: list[dict]) -> dict:
    """Did the agent search the catalog, and did it read repo code before (or instead of) searching?"""
    names = [c["tool"] for c in calls]
    reading = {"Read", "Grep", "Glob", "LS"}
    first_search = next((i for i, n in enumerate(names) if n == "mcp__pcat__search_patterns"), None)
    first_read = next((i for i, n in enumerate(names) if n in reading or n == "Bash"), None)
    return {
        "searched": first_search is not None,
        "read_repo": first_read is not None,
        "read_before_search": first_read is not None and (first_search is None or first_read < first_search),
        "fetched": [c["input"].get("id") for c in calls if c["tool"] == "mcp__pcat__get_pattern"],
        "checked": sum(1 for n in names if n == "mcp__pcat__check_code"),
        "tools": dict(sorted(__import__("collections").Counter(names).items())),
    }


def leaks(calls: list[dict], workdir: Path, forbidden: tuple[str, ...]) -> list[str]:
    """Tool inputs that mention a forbidden path (the original apps, the pcat repo)."""
    out = []
    for c in calls:
        text = json.dumps(c["input"])
        for f in forbidden:
            if f in text:
                out.append(f"{c['tool']}: {text[:160]}")
                break
    return out


# --------------------------------------------------------------------------- #
# Scoring one run
# --------------------------------------------------------------------------- #


def _functions_in(path: Path) -> list[tuple[str, ast.AST]]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError, ValueError, UnicodeDecodeError):
        return []
    return [(info.qualname, info.node) for info in provenance.functions(source, tree)]


def find_new_function(dest: Path, task: Task, changed: list[str], reference: str) -> dict | None:
    """The function the run wrote for the task: same name in the task's file, else the most
    similar function (to the removed original) in the changed Python files."""
    from pcat import variance

    ref_tree = ast.parse(reference)
    ref_node = next(n for n in ref_tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.name == task.entry)
    ref_text = provenance.shape_text(ref_node) or ""
    added = added_lines(dest)
    target = dest / task.file
    for qualname, node in _functions_in(target):
        if qualname == task.entry and _touched(node, added.get(task.file, set())):
            return {"path": task.file, "function": qualname, "how": "same name", "node": node}
    best = None
    for rel in changed:
        if not rel.endswith(".py"):
            continue
        for qualname, node in _functions_in(dest / rel):
            if not _touched(node, added.get(rel, set())):
                continue  # only functions the run added or changed
            text = provenance.shape_text(node)
            if text is None:
                continue
            sim = variance.similarity(text, ref_text)
            if best is None or sim > best[0]:
                best = (sim, {"path": rel, "function": qualname, "how": "most similar", "node": node})
    return best[1] if best else None


def added_lines(dest: Path) -> dict[str, set[int]]:
    """path -> new-side line numbers added or changed since the baseline commit (staged)."""
    from pcat import lint

    _git(dest, "add", "-A")
    out: dict[str, set[int]] = {}
    for rel in _git(dest, "diff", "--cached", "--name-only").split():
        out[rel] = lint.parse_diff_lines(_git(dest, "diff", "--cached", "--unified=0", "--no-color", "--", rel))
    return out


def _touched(node: ast.AST, lines: set[int]) -> bool:
    start = min([node.lineno, *(d.lineno for d in getattr(node, "decorator_list", []))])
    return any(start <= n <= node.end_lineno for n in lines)


def similarity_to_reference(node: ast.AST, reference: str, entry: str) -> float | None:
    from pcat import variance

    ref_tree = ast.parse(reference)
    ref_node = next(n for n in ref_tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.name == entry)
    a, b = provenance.shape_text(node), provenance.shape_text(ref_node)
    return None if a is None or b is None else round(variance.similarity(a, b), 4)


# --------------------------------------------------------------------------- #
# Summaries (Part F analysis)
# --------------------------------------------------------------------------- #


def _rate(n: int, d: int) -> float | None:
    return round(n / d, 3) if d else None


def _median(values: list[float]) -> float | None:
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    mid = len(values) // 2
    return round(values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2, 4)


def run_flags(r: dict) -> dict:
    """Per-run booleans used by the summaries."""
    nf = (r.get("score") or {}).get("new_function") or {}
    inferred = nf.get("inferred") or {}
    pattern = r.get("pattern")
    used = {p for p in (
        (nf.get("marker") or "").split("@")[0] or None,
        inferred.get("pattern") if inferred.get("derived") else None,
        nf.get("matches_pattern") if nf.get("status") in ("covered", "near") else None,
    ) if p}
    fetched = [f.split("@")[0] for f in (r.get("tool_order") or {}).get("fetched") or [] if f]
    lint = (r.get("score") or {}).get("lint") or {}
    return {
        "searched": bool((r.get("tool_order") or {}).get("searched")),
        "read_before_search": bool((r.get("tool_order") or {}).get("read_before_search")),
        "fetched_right": bool(pattern) and pattern in fetched,
        "fetched_any": bool(fetched),
        "matches": bool(pattern) and nf.get("status") in ("covered", "near") and nf.get("matches_pattern") == pattern,
        "derives": bool(pattern) and pattern in used,
        "marked": bool(nf.get("marker")),
        "used_some_pattern": bool(used),
        "found_function": bool(nf),
        "similarity": nf.get("similarity_to_original"),
        "lint_failed": bool(lint.get("failed")),
        "high": (lint.get("deviations") or {}).get("high", 0),
        "medium": (lint.get("deviations") or {}).get("medium", 0),
        "low": (lint.get("deviations") or {}).get("low", 0),
        "cost": (r.get("summary") or {}).get("cost_usd"),
        "seconds": r.get("wall_seconds"),
        "files": len(r.get("files_changed") or []),
        "leaked": bool(r.get("leaks")),
    }


def summarize_runs(records: list[dict]) -> dict:
    """Metrics for one group of runs (e.g. one app and condition)."""
    ok = [r for r in records if r.get("status") == "ok"]
    flags = [run_flags(r) for r in ok]
    pos = [f for f, r in zip(flags, ok) if r.get("kind") == "pattern"]
    neg = [f for f, r in zip(flags, ok) if r.get("kind") == "negative"]
    return {
        "runs": len(records), "ok": len(ok),
        "timeouts": sum(r.get("status") == "timeout" for r in records),
        "errors": sum(r.get("status") == "error" for r in records),
        "search_rate": _rate(sum(f["searched"] for f in flags), len(flags)),
        "read_before_search_rate": _rate(sum(f["read_before_search"] for f in flags if f["searched"]),
                                         sum(f["searched"] for f in flags)),
        "pattern_runs": len(pos),
        "fetched_right_rate": _rate(sum(f["fetched_right"] for f in pos), len(pos)),
        "matches_rate": _rate(sum(f["matches"] for f in pos), len(pos)),
        "derives_rate": _rate(sum(f["derives"] for f in pos), len(pos)),
        "marked_rate": _rate(sum(f["marked"] for f in pos), len(pos)),
        "found_function_rate": _rate(sum(f["found_function"] for f in flags), len(flags)),
        "median_similarity_pattern_tasks": _median([f["similarity"] for f in pos]),
        "median_similarity_negative_tasks": _median([f["similarity"] for f in neg]),
        "lint_fail_rate": _rate(sum(f["lint_failed"] for f in flags), len(flags)),
        "deviations": {k: sum(f[k] for f in flags) for k in ("high", "medium", "low")},
        "negative_runs": len(neg),
        "negatives_fetched_a_pattern": sum(f["fetched_any"] for f in neg),
        "negatives_used_a_pattern": sum(f["used_some_pattern"] for f in neg),
        "median_cost_usd": _median([f["cost"] for f in flags]),
        "total_cost_usd": round(sum(f["cost"] or 0 for f in flags), 2),
        "median_seconds": _median([f["seconds"] for f in flags]),
        "median_files_touched": _median([f["files"] for f in flags]),
        "runs_with_leaks": sum(f["leaked"] for f in flags),
    }
