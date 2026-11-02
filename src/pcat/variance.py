"""LLM output variance experiment (spec docs/specs/v2.1-variance-experiment.md).

Importable, unit-tested logic for `scripts/variance.py`: prompts, generator
backends, code extraction, snippet fingerprinting, metrics, reference
selection and the analysis document. Canonicalization and shape rules are used
unchanged; module-level code that the canonicalizer does not accept is handled
here by a separate, experiment-only normalization step (`normalize_snippet`).
"""

from __future__ import annotations

import ast
import difflib
import itertools
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from pcat import canonical, shape
from pcat.errors import PcatError

CONDITIONS = ("A", "B", "C")
REFERENCE_INSTRUCTION = (
    "Follow this reference implementation; adapt names and details only where the "
    "request requires it:"
)
DEFAULT_MODEL = "claude-sonnet-5-5"
SYNTHETIC_FUNCTION = "_module_level"


# --------------------------------------------------------------------------- #
# Tasks and prompts
# --------------------------------------------------------------------------- #


def load_tasks(path: Path) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    for name, task in data["tasks"].items():
        if len(task["paraphrases"]) != 5:
            raise PcatError(f"task {name}: expected 5 paraphrases")
    return data


def build_prompt(
    tasks: dict, task: str, condition: str, index: int, reference: str | None = None
) -> tuple[str, str]:
    """(prompt text, variant label) for sample `index` (0-based)."""
    spec = tasks["tasks"][task]
    suffix = tasks["suffix"].strip()
    if condition == "A":
        return f"{spec['prompt'].strip()}\n\n{suffix}", "prompt"
    k = index % len(spec["paraphrases"])
    base = spec["paraphrases"][k].strip()
    if condition == "B":
        return f"{base}\n\n{suffix}", f"paraphrase-{k + 1}"
    if condition == "C":
        if reference is None:
            raise PcatError(f"condition C for {task} needs a reference implementation")
        ref = reference.strip("\n")
        text = f"{base}\n\n{REFERENCE_INSTRUCTION}\n\n```python\n{ref}\n```\n\n{suffix}"
        return text, f"paraphrase-{k + 1}+reference"
    raise PcatError(f"unknown condition {condition!r}")


# --------------------------------------------------------------------------- #
# Generator backends
# --------------------------------------------------------------------------- #


@dataclass
class Generation:
    text: str
    model: str | None
    temperature: float | None
    extra: dict = field(default_factory=dict)


class GenerationError(Exception):
    """A generation attempt failed (may be retried)."""


def select_backend(env: dict | None = None, which=shutil.which) -> str:
    """First available backend, in the spec's order: api, cli, subagent.

    "subagent" cannot be run from this script: it means a Claude session must
    generate each sample with a fresh subagent and store it with `ingest`.
    """
    env = os.environ if env is None else env
    if env.get("ANTHROPIC_API_KEY"):
        return "api"
    if which("claude"):
        return "cli"
    return "subagent"


class ApiGenerator:
    """Anthropic Messages API, one request per sample, default temperature."""

    backend = "api"

    def __init__(self, model: str, api_key: str, base_url: str = "https://api.anthropic.com"):
        self.model, self.api_key, self.base_url = model, api_key, base_url.rstrip("/")

    def generate(self, prompt: str) -> Generation:
        body = json.dumps(
            {"model": self.model, "max_tokens": 8192, "messages": [{"role": "user", "content": prompt}]}
        ).encode()
        request = urllib.request.Request(
            f"{self.base_url}/v1/messages",
            data=body,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                data = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise GenerationError(f"API request failed: {exc}") from None
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        if not text:
            raise GenerationError("empty API response")
        return Generation(text, data.get("model", self.model), None, {"usage": data.get("usage")})


# Tools are disallowed so a sample is a single model turn; variables that would
# load extra CLAUDE.md files into the child are removed from its environment.
CLI_DISALLOWED_TOOLS = (
    "Bash", "Edit", "Write", "Read", "Glob", "Grep", "WebFetch", "WebSearch",
    "NotebookEdit", "Agent", "Task",
)
CLI_STRIPPED_ENV = ("CLAUDE_ADDITIONAL_DIRECTORIES", "CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD")


class CliGenerator:
    """Headless Claude Code (`claude -p`): one fresh process per sample."""

    backend = "cli"

    def __init__(self, model: str, workdir: Path, timeout: int = 600):
        self.model, self.workdir, self.timeout = model, Path(workdir), timeout

    def command(self, prompt: str) -> list[str]:
        return [
            "claude", "-p", prompt,
            "--output-format", "json",
            "--no-session-persistence",
            "--strict-mcp-config",
            "--model", self.model,
            "--disallowedTools", *CLI_DISALLOWED_TOOLS,
        ]

    def generate(self, prompt: str) -> Generation:
        self.workdir.mkdir(parents=True, exist_ok=True)
        env = {k: v for k, v in os.environ.items() if k not in CLI_STRIPPED_ENV}
        try:
            proc = subprocess.run(
                self.command(prompt), cwd=self.workdir, env=env,
                capture_output=True, text=True, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            raise GenerationError(f"claude -p timed out after {self.timeout}s") from None
        if proc.returncode != 0:
            raise GenerationError(f"claude -p exited {proc.returncode}: {proc.stderr.strip()[:300]}")
        try:
            data = json.loads(proc.stdout)
        except ValueError:
            raise GenerationError(f"claude -p returned non-JSON: {proc.stdout[:200]!r}") from None
        if data.get("is_error") or not data.get("result"):
            raise GenerationError(f"claude -p error: {str(data.get('result'))[:300]}")
        usage = data.get("modelUsage") or {}
        # The CLI may also call a small model for housekeeping; report the main one.
        model = max(usage, key=lambda m: usage[m].get("outputTokens", 0)) if usage else self.model
        return Generation(
            data["result"],
            model,
            None,
            {
                "num_turns": data.get("num_turns"),
                "duration_ms": data.get("duration_ms"),
                "cost_usd": data.get("total_cost_usd"),
            },
        )


def generate_with_retries(generator, prompt: str, retries: int = 3, sleep=time.sleep):
    """(Generation or None, attempts, last error). Transient failures are retried."""
    error = None
    for attempt in range(1, retries + 2):
        try:
            return generator.generate(prompt), attempt, None
        except GenerationError as exc:
            error = str(exc)
            if attempt <= retries:
                sleep(5 * 2 ** (attempt - 1))
    return None, retries + 1, error


# --------------------------------------------------------------------------- #
# Code extraction and validity
# --------------------------------------------------------------------------- #

_FENCE = re.compile(r"```[ \t]*([A-Za-z0-9_+-]*)[^\n]*\n(.*?)```", re.DOTALL)
_PYTHON_TAGS = {"python", "py", "python3", ""}


def extract_code(response: str) -> str:
    """First fenced Python code block (untagged fences count), else the whole response."""
    for match in _FENCE.finditer(response):
        if match.group(1).lower() in _PYTHON_TAGS:
            return match.group(2).rstrip() + "\n"
    return response.strip() + "\n"


def check_code(code: str) -> str | None:
    """None if valid, else the reason it is invalid."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError) as exc:
        return f"syntax_error: {getattr(exc, 'msg', None) or exc}"
    if any(isinstance(n, ast.ClassDef) for n in ast.walk(tree)):
        return "contains_class"
    if not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in tree.body):
        return "no_function"
    return None


# --------------------------------------------------------------------------- #
# Snippet normalization and fingerprints
# --------------------------------------------------------------------------- #

_FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)
_IMPORT_TYPES = (ast.Import, ast.ImportFrom)


@dataclass(frozen=True)
class SnippetInfo:
    exact_fingerprint: str
    shape_fingerprint: str
    canonical_text: str
    imports: tuple[str, ...]
    third_party: tuple[str, ...]
    functions: int
    entry_params: int
    module_statements: int  # non-literal module-level statements moved aside


def _is_main_guard(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.If)
        and isinstance(stmt.test, ast.Compare)
        and isinstance(stmt.test.left, ast.Name)
        and stmt.test.left.id == "__name__"
    )


def import_roots(tree: ast.AST) -> tuple[str, ...]:
    """Sorted top-level module names imported anywhere (`from jwt import x` -> jwt)."""
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            roots.add(node.module.split(".")[0])
    roots.discard("__future__")
    return tuple(sorted(roots))


def third_party(roots: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(r for r in roots if r not in sys.stdlib_module_names)


class _GlobalRenamer(ast.NodeTransformer):
    """Rename module globals (gmap) except where a function binds the name locally."""

    def __init__(self, gmap: dict[str, str]):
        self.gmap = gmap
        self.shadowed: set[str] = set()

    def visit_Name(self, node: ast.Name) -> ast.Name:  # noqa: N802
        if node.id in self.gmap and node.id not in self.shadowed:
            node.id = self.gmap[node.id]
        return node

    def visit_Global(self, node: ast.Global) -> ast.Global:  # noqa: N802
        node.names = [self.gmap.get(n, n) for n in node.names]
        return node

    def visit_function(self, func: ast.FunctionDef) -> None:
        for part in [*func.decorator_list, *func.args.defaults, func.returns]:
            if part is not None:
                self.visit(part)
        for d in func.args.kw_defaults:
            if d is not None:
                self.visit(d)
        for arg in canonical._arg_nodes(func.args):
            if arg.annotation is not None:
                self.visit(arg.annotation)
        scope = canonical._scope_names(func)
        self.shadowed = scope.locals | scope.imported
        for stmt in func.body:
            self.visit(stmt)
        self.shadowed = set()


def normalize_snippet(code: str, drop_classes: bool = False) -> tuple[str, int]:
    """Rewrite a sample so the unchanged canonicalizer accepts it.

    - `if __name__ == "__main__":` blocks are dropped (demo code, not the answer)
    - other top-level statements that are not imports, functions or literal
      constants (`app = FastAPI()`, `ctx = CryptContext(...)`) are moved, in
      order, into a synthetic last function `_module_level`, and the names they
      bind are renamed g0, g1, ... everywhere (so a global's name does not
      matter, like a local's) and declared `global` there.
    - with `drop_classes` (supplementary metric only), top-level classes are
      removed and their names are treated like such globals.

    Returns (source for canonical.analyze, number of statements moved).
    """
    tree = ast.parse(code)
    kept: list[ast.stmt] = []
    moved: list[ast.stmt] = []
    bound: list[str] = []
    for stmt in tree.body:
        if _is_main_guard(stmt):
            continue
        if drop_classes and isinstance(stmt, ast.ClassDef):
            if stmt.name not in bound:
                bound.append(stmt.name)
            continue
        if canonical._is_string_expr(stmt) and not kept and not moved:
            continue  # module docstring
        if isinstance(stmt, (*_IMPORT_TYPES, *_FUNC_TYPES)) or canonical._is_literal_constant(stmt):
            kept.append(stmt)
        else:
            moved.append(stmt)

    for stmt in moved:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id not in bound:
                bound.append(node.id)
    gmap = {name: f"g{i}" for i, name in enumerate(bound)}
    renamer = _GlobalRenamer(gmap)
    for stmt in kept:
        if isinstance(stmt, _FUNC_TYPES):
            renamer.visit_function(stmt)
    for stmt in moved:
        renamer.visit(stmt)

    body = list(kept)
    if moved:
        prologue = [ast.Global(names=sorted(gmap.values(), key=lambda g: int(g[1:])))] if gmap else []
        body.append(
            ast.FunctionDef(
                name=SYNTHETIC_FUNCTION,
                args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                body=[*prologue, *moved],
                decorator_list=[],
                returns=None,
                type_params=[],
            )
        )
    module = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(module)
    return ast.unparse(module), len(moved)


def snippet_info(code: str, drop_classes: bool = False) -> SnippetInfo:
    """Fingerprints and descriptors of a valid sample (raises PcatError if impossible)."""
    tree = ast.parse(code)
    funcs = [n for n in tree.body if isinstance(n, _FUNC_TYPES)]
    entry = funcs[0]
    args = entry.args
    params = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
    params += (args.vararg is not None) + (args.kwarg is not None)
    source, moved = normalize_snippet(code, drop_classes)
    result = canonical.analyze(source)
    shape_text = shape.shape_text_from_canonical(result.text)
    roots = import_roots(tree)
    return SnippetInfo(
        exact_fingerprint=result.fingerprint,
        shape_fingerprint=canonical.fingerprint(shape_text),
        canonical_text=result.text,
        imports=roots,
        third_party=third_party(roots),
        functions=len(funcs),
        entry_params=params,
        module_statements=moved,
    )


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #


def distribution_metrics(values: list[str]) -> dict:
    """Distinct values, top share and effective number (exp of Shannon entropy)."""
    n = len(values)
    if n == 0:
        return {"distinct": 0, "top_share": 0.0, "effective": 0.0}
    counts = Counter(values)
    entropy = -sum((c / n) * math.log(c / n) for c in counts.values())
    return {
        "distinct": len(counts),
        "top_share": round(max(counts.values()) / n, 4),
        "effective": round(math.exp(entropy), 2),
    }


NEAR_SHAPE_THRESHOLD = 0.9


def similarity(a: str, b: str) -> float:
    """difflib ratio of two shape texts (1.0 = identical)."""
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def similarity_metrics(texts: list[str]) -> dict:
    """Supplementary: how *different* distinct shapes are.

    Exact shape equality counts a one-token difference as a new shape, so this
    adds the median pairwise similarity and the number of near-shape groups
    (single-linkage clusters of samples with similarity >= NEAR_SHAPE_THRESHOLD).
    """
    n = len(texts)
    if n < 2:
        return {"median_similarity": 1.0 if n else 0.0, "near_shape_groups": n}
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    sims = []
    for i, j in itertools.combinations(range(n), 2):
        sim = 1.0 if texts[i] == texts[j] else similarity(texts[i], texts[j])
        sims.append(sim)
        if sim >= NEAR_SHAPE_THRESHOLD:
            parent[find(i)] = find(j)
    sims.sort()
    mid = len(sims) // 2
    median = sims[mid] if len(sims) % 2 else (sims[mid - 1] + sims[mid]) / 2
    return {
        "median_similarity": round(median, 3),
        "near_shape_groups": len({find(i) for i in range(n)}),
    }


def _histogram(values) -> dict:
    return {str(k): v for k, v in sorted(Counter(values).items(), key=lambda kv: str(kv[0]))}


# --------------------------------------------------------------------------- #
# Samples on disk
# --------------------------------------------------------------------------- #


def sample_paths(run_dir: Path, task: str, condition: str, number: int) -> tuple[Path, Path]:
    folder = Path(run_dir) / task / condition
    return folder / f"sample_{number:02d}.py", folder / f"sample_{number:02d}.json"


def load_samples(run_dir: Path, task: str, condition: str) -> list[dict]:
    folder = Path(run_dir) / task / condition
    if not folder.is_dir():
        return []
    return [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("sample_*.json"))
    ]


def analyze_sample(record: dict) -> dict:
    """Per-sample analysis row (no timestamps or other run-dependent data)."""
    row = {"sample": record["sample"], "status": record["status"]}
    if record["status"] != "ok":
        row["invalid_reason"] = "generation_failed"
        return row
    reason = check_code(record["code"])
    if reason is None:
        try:
            info = snippet_info(record["code"])
        except (PcatError, RecursionError, ValueError, SyntaxError) as exc:
            reason = f"cannot_fingerprint: {exc}"
        else:
            row.update(
                {
                    "exact_fingerprint": info.exact_fingerprint,
                    "shape_fingerprint": info.shape_fingerprint,
                    "shape_text": shape.shape_text_from_canonical(info.canonical_text),
                    "imports": list(info.imports),
                    "third_party": list(info.third_party),
                    "functions": info.functions,
                    "entry_params": info.entry_params,
                    "module_statements": info.module_statements,
                }
            )
    if reason is not None:
        row["invalid_reason"] = reason
    # Supplementary metric (not part of the spec's validity rule): samples whose
    # only problem is top-level classes (e.g. Pydantic models) are fingerprinted
    # with those classes removed.
    if "invalid_reason" not in row:
        row["classes_removed"] = {"shape_fingerprint": row["shape_fingerprint"], "classes": 0}
    elif reason == "contains_class" and _only_top_level_classes(record["code"]):
        try:
            info = snippet_info(record["code"], drop_classes=True)
        except (PcatError, RecursionError, ValueError, SyntaxError, IndexError):
            pass
        else:
            classes = sum(isinstance(n, ast.ClassDef) for n in ast.parse(record["code"]).body)
            row["classes_removed"] = {
                "shape_fingerprint": info.shape_fingerprint,
                "classes": classes,
                "third_party": list(info.third_party),
            }
    return row


def _only_top_level_classes(code: str) -> bool:
    tree = ast.parse(code)
    top = {id(n) for n in tree.body if isinstance(n, ast.ClassDef)}
    return all(id(n) in top for n in ast.walk(tree) if isinstance(n, ast.ClassDef))


def _reason_key(reason: str) -> str:
    return reason.split(":", 1)[0]


def summarize(rows: list[dict]) -> dict:
    valid = [r for r in rows if "invalid_reason" not in r]
    invalid = Counter(_reason_key(r["invalid_reason"]) for r in rows if "invalid_reason" in r)
    exact = distribution_metrics([r["exact_fingerprint"] for r in valid])
    shapes = distribution_metrics([r["shape_fingerprint"] for r in valid])
    imports = distribution_metrics(["+".join(r["imports"]) for r in valid])
    libs = distribution_metrics(["+".join(r["third_party"]) for r in valid])
    return {
        "samples": len(rows),
        "valid": len(valid),
        "invalid": dict(sorted(invalid.items())),
        "distinct_exact": exact["distinct"],
        "distinct_shapes": shapes["distinct"],
        "top_shape_share": shapes["top_share"],
        "effective_shapes": shapes["effective"],
        "distinct_import_sets": imports["distinct"],
        "distinct_third_party_sets": libs["distinct"],
        "import_sets": _histogram("+".join(r["imports"]) or "(none)" for r in valid),
        "third_party_sets": _histogram("+".join(r["third_party"]) or "(none)" for r in valid),
        "function_counts": _histogram(r["functions"] for r in valid),
        "entry_param_counts": _histogram(r["entry_params"] for r in valid),
        "with_module_statements": sum(1 for r in valid if r["module_statements"]),
        **similarity_metrics([r["shape_text"] for r in valid]),
        "supplementary_classes_removed": _classes_removed_summary(rows),
    }


def _classes_removed_summary(rows: list[dict]) -> dict:
    """Shape metrics over valid samples plus samples whose only issue is top-level classes."""
    covered = [r["classes_removed"] for r in rows if "classes_removed" in r]
    metrics = distribution_metrics([c["shape_fingerprint"] for c in covered])
    return {
        "samples": len(covered),
        "with_classes": sum(1 for c in covered if c["classes"]),
        "distinct_shapes": metrics["distinct"],
        "top_shape_share": metrics["top_share"],
        "effective_shapes": metrics["effective"],
    }


# --------------------------------------------------------------------------- #
# References (condition C)
# --------------------------------------------------------------------------- #


def select_reference(rows: list[dict]) -> int:
    """Sample number of the representative of the most common shape.

    Most common shape (ties: the shape whose earliest sample is lowest), then
    its largest exact sub-group (same tie-break), then the lowest sample number.
    """
    valid = [r for r in rows if "invalid_reason" not in r]
    if not valid:
        raise PcatError("no valid samples to pick a reference from")

    def best_group(items: list[dict], key: str) -> list[dict]:
        groups: dict[str, list[dict]] = {}
        for r in items:
            groups.setdefault(r[key], []).append(r)
        return min(groups.values(), key=lambda g: (-len(g), min(r["sample"] for r in g)))

    group = best_group(best_group(valid, "shape_fingerprint"), "exact_fingerprint")
    return min(r["sample"] for r in group)


# --------------------------------------------------------------------------- #
# Analysis document
# --------------------------------------------------------------------------- #


def analyze_run(run_dir: Path, tasks: list[str], references: dict | None = None) -> dict:
    """Analysis of every task/condition present in `run_dir` (deterministic)."""
    out: dict = {
        "canonical_version": canonical.CANONICAL_VERSION,
        "shape_version": shape.SHAPE_VERSION,
        "tasks": {},
    }
    for task in tasks:
        per_condition = {}
        for condition in CONDITIONS:
            records = load_samples(run_dir, task, condition)
            if not records:
                continue
            rows = [analyze_sample(r) for r in records]
            summary = summarize(rows)
            ref = (references or {}).get(task)
            if condition == "C" and ref:
                valid = [r for r in rows if "invalid_reason" not in r]
                hits = sum(1 for r in valid if r["shape_fingerprint"] == ref["shape_fingerprint"])
                summary["reference_match_rate"] = round(hits / len(valid), 4) if valid else 0.0
                summary["reference_exact_match_rate"] = (
                    round(
                        sum(1 for r in valid if r["exact_fingerprint"] == ref["exact_fingerprint"])
                        / len(valid),
                        4,
                    )
                    if valid
                    else 0.0
                )
            per_condition[condition] = {"summary": summary, "samples": rows}
        if per_condition:
            out["tasks"][task] = per_condition
    return out


def analysis_json_text(analysis: dict) -> str:
    return json.dumps(analysis, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def headline_table(analysis: dict) -> str:
    """Markdown table: task x condition."""
    lines = [
        "| Task | Cond. | Valid | Distinct exact | Distinct shapes | Top-shape share "
        "| Effective shapes | Import sets | 3rd-party sets | Ref. match |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for task, conds in analysis["tasks"].items():
        for condition, data in conds.items():
            s = data["summary"]
            ref = s.get("reference_match_rate")
            lines.append(
                f"| {task} | {condition} | {s['valid']}/{s['samples']} | {s['distinct_exact']} "
                f"| {s['distinct_shapes']} | {s['top_shape_share']:.2f} | {s['effective_shapes']:.2f} "
                f"| {s['distinct_import_sets']} | {s['distinct_third_party_sets']} "
                f"| {'' if ref is None else f'{ref:.2f}'} |"
            )
    return "\n".join(lines) + "\n"
