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
