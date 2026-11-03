"""Where a function came from (v4 Part A): explicit markers and inferred provenance.

Marker: a comment line `# pcat: <pattern-id>[@v<version>]` in the comment block
directly above a function (above its decorators, if any). `get_pattern` writes
one above the entry point and every export. Approvals (`# pcat-allow: PC101 --
reason`) live in the same block; they are parsed here and judged in `lint.py`.

Inference: an unmarked function is *likely derived* from the most similar
catalog function (entry point or export of an active pattern) when the v2.1
similarity of their shape texts is at least INFERENCE_THRESHOLD. Inferred
provenance is advisory: it never fails CI.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from pcat import miner, variance
from pcat.errors import PcatError

# Calibrated in v4 Part A on existing data only (scripts/lint_eval.py calibrate;
# experiments/linter/inference_calibration.json). See DECISIONS.md.
INFERENCE_THRESHOLD = 0.56  # midpoint of the best range: 199/200 derived, 1/187 not derived

MARKER_RE = re.compile(r"^#\s*pcat\s*:\s*(?P<id>\S+?)(?:@v(?P<version>\d+))?\s*$")
ALLOW_RE = re.compile(r"^#\s*pcat-allow\s*:\s*(?P<rest>.*)$")
_ALLOW_BODY_RE = re.compile(r"^(?P<code>PC\d{3})\s*(?:--\s*(?P<reason>.*))?$")
_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
MIN_REASON_LENGTH = 10


@dataclass(frozen=True)
class Marker:
    pattern_id: str
    version: int | None
    line: int

    @property
    def ref(self) -> str:
        return self.pattern_id if self.version is None else f"{self.pattern_id}@v{self.version}"


@dataclass(frozen=True)
class Approval:
    code: str | None
    reason: str
    line: int
    problem: str | None = None  # why the approval is invalid, if it is


@dataclass
class FunctionInfo:
    node: ast.FunctionDef
    qualname: str
    kind: str  # function | method | nested
    start: int  # first line (first decorator or def)
    markers: list[Marker] = field(default_factory=list)
    approvals: list[Approval] = field(default_factory=list)
    problems: list[tuple[int, str]] = field(default_factory=list)  # (line, message)

    @property
    def marker(self) -> Marker | None:
        return self.markers[0] if self.markers else None


def marker_line(pattern_id: str, version: int) -> str:
    return f"# pcat: {pattern_id}@v{version}"


def add_markers(code: str, marker: str, names: list[str]) -> str:
    """Insert `marker` on its own line directly above each top-level `def <name>(`."""
    wanted = set(names)
    out = []
    for line in code.splitlines(keepends=True):
        m = re.match(r"^(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", line)
        if m and m.group(1) in wanted:
            out.append(marker + "\n")
        out.append(line)
    return "".join(out)


def comment_block(lines: list[str], start: int) -> list[tuple[int, str]]:
    """(line number, stripped text) of the comment lines directly above line `start`."""
    out = []
    i = start - 2
    while i >= 0 and lines[i].strip().startswith("#"):
        out.append((i + 1, lines[i].strip()))
        i -= 1
    return list(reversed(out))


def parse_block(block: list[tuple[int, str]]) -> tuple[list[Marker], list[Approval], list[tuple[int, str]]]:
    markers: list[Marker] = []
    approvals: list[Approval] = []
    problems: list[tuple[int, str]] = []
    for line, text in block:
        allow = ALLOW_RE.match(text)
        if allow:
            approvals.append(parse_approval(allow.group("rest"), line))
            continue
        if re.match(r"^#\s*pcat\s*:", text):
            m = MARKER_RE.match(text)
            if not m or not _ID_RE.match(m.group("id")):
                problems.append((line, f"malformed pcat marker: {text!r} "
                                       "(expected '# pcat: <pattern-id>@v<version>')"))
                continue
            version = int(m.group("version")) if m.group("version") else None
            markers.append(Marker(m.group("id"), version, line))
    if len(markers) > 1:
        problems.append((markers[1].line, "more than one pcat marker; the first one is used"))
    return markers, approvals, problems


def parse_approval(rest: str, line: int) -> Approval:
    m = _ALLOW_BODY_RE.match(rest.strip())
    if not m:
        return Approval(None, "", line, "malformed approval: expected "
                                        "'# pcat-allow: PC101 -- reason' (one code per line)")
    reason = (m.group("reason") or "").strip()
    if not reason:
        return Approval(m.group("code"), "", line, "approval has no reason (add '-- <reason>')")
    if len(reason) < MIN_REASON_LENGTH:
        return Approval(m.group("code"), reason, line,
                        f"approval reason is shorter than {MIN_REASON_LENGTH} characters")
    return Approval(m.group("code"), reason, line)


def functions(source: str, tree: ast.Module | None = None) -> list[FunctionInfo]:
    """Every function in `source` with its markers, approvals and comment problems."""
    tree = tree if tree is not None else ast.parse(source)
    lines = source.splitlines()
    collector = miner._FunctionCollector()
    collector.visit(tree)
    out = []
    for node, qualname, kind, _ in collector.found:
        start = min([node.lineno, *(d.lineno for d in node.decorator_list)])
        markers, approvals, problems = parse_block(comment_block(lines, start))
        out.append(FunctionInfo(node, qualname, kind, start, markers, approvals, problems))
    return out


# --------------------------------------------------------------------------- #
# Inference
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Reference:
    pattern_id: str
    version: int
    function: str
    shape_text: str

    @property
    def key(self) -> str:
        return f"{self.pattern_id}@v{self.version}"


@dataclass(frozen=True)
class Inference:
    pattern_id: str
    version: int
    function: str
    similarity: float
    derived: bool  # similarity >= threshold


def references(root: Path, include_deprecated: bool = False) -> list[Reference]:
    """Shape texts of every catalog entry point and export (active patterns by default)."""
    from pcat import catalog as cat

    out = []
    for pattern in cat.load_catalog(root):
        meta = pattern.meta
        if meta is None or (meta.status != "active" and not include_deprecated):
            continue
        tree = ast.parse(pattern.impl_path.read_text(encoding="utf-8"))
        wanted = [meta.entry_point, *meta.exports]
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted:
                out.append(Reference(meta.id, meta.version, node.name,
                                     miner.mine_function(node)["shape_text"]))
    return sorted(out, key=lambda r: (r.pattern_id, r.version, r.function))


def shape_text(node: ast.FunctionDef) -> str | None:
    try:
        return miner.mine_function(node)["shape_text"]
    except (PcatError, RecursionError):
        return None


def rank(text: str, refs: list[Reference]) -> list[tuple[float, Reference]]:
    """Similarity to every reference, best first (ties by pattern id and function)."""
    scored = [(round(variance.similarity(text, r.shape_text), 4), r) for r in refs]
    return sorted(scored, key=lambda x: (-x[0], x[1].pattern_id, x[1].version, x[1].function))


def infer(node: ast.FunctionDef, refs: list[Reference], threshold: float | None = None) -> Inference | None:
    """Most similar catalog function for `node`, or None when it has no shape."""
    text = shape_text(node)
    if text is None or not refs:
        return None
    best = _best(text, refs)
    cutoff = INFERENCE_THRESHOLD if threshold is None else threshold
    sim, ref = best
    return Inference(ref.pattern_id, ref.version, ref.function, sim, sim >= cutoff)


def _best(text: str, refs: list[Reference]) -> tuple[float, Reference]:
    import difflib

    best: tuple[float, Reference] | None = None
    for ref in sorted(refs, key=lambda r: (r.pattern_id, r.version, r.function)):
        matcher = difflib.SequenceMatcher(None, text, ref.shape_text, autojunk=False)
        if best is not None and matcher.real_quick_ratio() < best[0]:
            continue
        if best is not None and matcher.quick_ratio() < best[0]:
            continue
        sim = round(matcher.ratio(), 4)
        if best is None or sim > best[0]:
            best = (sim, ref)
    assert best is not None
    return best
