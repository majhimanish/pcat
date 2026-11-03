"""`pcat lint`: deviations of derived code from catalog patterns (v4 Part D).

Scans Python files with the miner's discovery and filters, finds functions
marked `# pcat: <id>@v<N>` (and, with include_inferred, unmarked functions that
are likely derived), analyzes their deviations (`deviation.py`) and applies
`# pcat-allow: PCxxx -- reason` approvals from the comment block above each
function. Only unapproved deviations on *marked* code at or above `fail_on`
fail; inferred findings are advisory. Library code: no printing or exiting.
"""

from __future__ import annotations

import ast
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from pcat import catalog as cat
from pcat import deviation, miner, provenance
from pcat.errors import PcatError

FAIL_LEVELS = ("high", "medium", "low", "never")
FORMATS = ("text", "json", "github")


@dataclass
class Finding:
    path: str
    function: str  # qualname
    line: int
    provenance: str  # "marked" | "inferred"
    pattern: str  # pattern key
    pattern_function: str
    similarity: float | None
    deviations: list[dict]  # deviation dicts + approved/approval
    stale_approvals: list[dict] = field(default_factory=list)
    diff: str = ""
    deprecated: str | None = None  # replaced_by when the marked pattern is deprecated
    hash: str | None = None  # v4.1: the function's current hash, for approvals
    approvals: list[dict] = field(default_factory=list)  # every approval with its state

    def failing(self, fail_on: str) -> list[dict]:
        if self.provenance != "marked" or fail_on == "never":
            return []
        bar = deviation.SEVERITY_RANK[fail_on]
        return [d for d in self.deviations
                if not d["approved"] and deviation.SEVERITY_RANK[d["severity"]] >= bar]

    def to_dict(self) -> dict:
        return {
            "path": self.path, "function": self.function, "line": self.line,
            "provenance": self.provenance, "pattern": self.pattern,
            "pattern_function": self.pattern_function, "similarity": self.similarity,
            "deviations": self.deviations, "stale_approvals": self.stale_approvals,
            "diff": self.diff, "deprecated": self.deprecated, "hash": self.hash,
            "approvals": self.approvals,
        }


@dataclass
class Message:
    path: str
    line: int
    level: str  # error | warning
    text: str


@dataclass
class Report:
    findings: list[Finding]
    messages: list[Message]
    files: int
    fail_on: str
    include_inferred: bool
    base_ref: str | None = None

    @property
    def approvals(self) -> list[dict]:
        return [a for f in self.findings for a in f.approvals]

    @property
    def proposals(self) -> list[dict]:
        return [a for a in self.approvals if a["state"] == "proposed"]

    @property
    def failed(self) -> bool:
        if self.fail_on == "never":
            return False
        return any(f.failing(self.fail_on) for f in self.findings) or any(
            m.level == "error" for m in self.messages)

    def to_dict(self) -> dict:
        counts = {s: 0 for s in ("high", "medium", "low")}
        for f in self.findings:
            for d in f.deviations:
                counts[d["severity"]] += 1
        return {
            "files": self.files, "fail_on": self.fail_on, "include_inferred": self.include_inferred,
            "failed": self.failed, "base_ref": self.base_ref,
            "approval_states": "confirmed/proposed relative to base_ref" if self.base_ref
            else "no base ref: approvals treated as confirmed",
            "summary": {"functions": len(self.findings),
                        "marked": sum(f.provenance == "marked" for f in self.findings),
                        "inferred": sum(f.provenance == "inferred" for f in self.findings),
                        "deviations": counts,
                        "failing": sum(len(f.failing(self.fail_on)) for f in self.findings)},
            "findings": [f.to_dict() for f in self.findings],
            "messages": [m.__dict__ for m in self.messages],
        }


# --------------------------------------------------------------------------- #
# Catalog access
# --------------------------------------------------------------------------- #


class Catalog:
    def __init__(self, root: Path):
        self.root = root
        self.patterns = [p for p in cat.load_catalog(root) if p.meta is not None]
        self._refs: list[provenance.Reference] | None = None

    def resolve(self, marker: provenance.Marker):
        found = cat.resolve(self.patterns, marker.ref)
        if not found:
            return None
        if marker.version is None:
            active = [p for p in found if p.meta.status == "active"]
            return (active or found)[-1]
        return found[-1]

    def by_key(self, pattern_id: str, version: int):
        found = cat.resolve(self.patterns, f"{pattern_id}@v{version}")
        return found[-1] if found else None

    @property
    def refs(self) -> list[provenance.Reference]:
        if self._refs is None:
            self._refs = provenance.references(self.root)
        return self._refs


# --------------------------------------------------------------------------- #
# Linting one source
# --------------------------------------------------------------------------- #


def apply_approvals(info: provenance.FunctionInfo, devs: list[deviation.Deviation], path: str, *,
                    current_hash: str | None, base_keys: set[tuple] | None = None,
                    confirmed_proposals: bool = False) -> tuple[list[dict], list[dict], list[Message], list[dict]]:
    """Apply the `# pcat-allow` lines of one function (v4.1 states).

    An approval is *stale* when it has no hash (v4 format) or its hash differs
    from the function's current hash, or its code no longer occurs; stale ones
    approve nothing. A current one is *confirmed* when `base_keys` is None (no
    base ref) or the same (function, code, hash) existed at the base ref, else
    *proposed*: it approves nothing unless `confirmed_proposals` (a human
    confirmed the pull request). Returns (deviation dicts, stale approvals,
    messages, every approval with its state).
    """
    messages = []
    current: dict[str, tuple[provenance.Approval, str]] = {}
    records: list[dict] = []
    stale: list[dict] = []
    present = {d.code for d in devs}
    for a in info.approvals:
        record = {"function": info.qualname, "path": path, "line": a.line, "code": a.code,
                  "hash": a.hash, "current_hash": current_hash, "reason": a.reason}
        if a.problem:
            messages.append(Message(path, a.line, "warning", f"{a.problem}; it approves nothing"))
            records.append({**record, "state": "invalid"})
            continue
        if a.code not in deviation.SEVERITY:
            messages.append(Message(path, a.line, "warning", f"unknown deviation code {a.code}"))
            records.append({**record, "state": "invalid"})
            continue
        why = None
        if a.hash is None:
            why = (f"stale approval: {a.code} in `{info.qualname}` has no code hash (v4 format); if the "
                   f"current code is approved, write: {provenance.approval_line(a.code, current_hash, a.reason)}")
        elif a.hash != current_hash:
            why = (f"stale approval: {a.code} #{a.hash} in `{info.qualname}` was given for different code "
                   f"(the function's hash is now #{current_hash}); it approves nothing until re-approved")
        elif a.code not in present:
            why = f"stale approval: {a.code} no longer occurs in `{info.qualname}`"
        if why:
            messages.append(Message(path, a.line, "warning", why))
            item = {**record, "state": "stale", "why": why}
            records.append(item)
            stale.append(item)
            continue
        state = "confirmed" if base_keys is None or (info.qualname, a.code, a.hash) in base_keys else "proposed"
        records.append({**record, "state": state})
        if a.code not in current or state == "confirmed":
            current[a.code] = (a, state)
    out = []
    for d in devs:
        item = d.to_dict()
        found = current.get(d.code)
        state = found[1] if found else None
        item["approved"] = state == "confirmed" or (state == "proposed" and confirmed_proposals)
        item["approval"] = found[0].reason if found else None
        item["approval_state"] = state
        item["hash"] = current_hash
        out.append(item)
    return out, stale, messages, records


def lint_source(source: str, path: str, catalog: Catalog, include_inferred: bool,
                lines: set[int] | None = None, base_keys: set[tuple] | None = None,
                confirmed_proposals: bool = False) -> tuple[list[Finding], list[Message]]:
    """Findings for one file's source. `lines`: only functions touching these lines."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError) as exc:
        return [], [Message(path, getattr(exc, "lineno", None) or 1, "warning",
                            f"cannot parse: {getattr(exc, 'msg', exc)}")]
    findings: list[Finding] = []
    messages: list[Message] = []
    for info in provenance.functions(source, tree):
        span_start = min([info.start, *(ln for ln, _ in info.problems),
                          *(m.line for m in info.markers), *(a.line for a in info.approvals)])
        if lines is not None and not any(span_start <= ln <= info.node.end_lineno for ln in lines):
            continue
        for line, problem in info.problems:
            messages.append(Message(path, line, "warning", problem))
        pattern, function, similarity, kind = None, None, None, None
        if info.marker is not None:
            pattern = catalog.resolve(info.marker)
            if pattern is None:
                messages.append(Message(path, info.marker.line, "error",
                                        f"`{info.qualname}` is marked with unknown pattern {info.marker.ref}"))
                continue
            kind = "marked"
        elif include_inferred:
            inf = provenance.infer(info.node, catalog.refs)
            if inf is None or not inf.derived:
                continue
            pattern = catalog.by_key(inf.pattern_id, inf.version)
            function, similarity, kind = inf.function, inf.similarity, "inferred"
        else:
            continue
        try:
            analysis = deviation.analyze_function(tree, info.node, pattern, function)
        except (PcatError, KeyError, RecursionError, ValueError) as exc:
            messages.append(Message(path, info.node.lineno, "warning",
                                    f"cannot analyze `{info.qualname}`: {exc}"))
            continue
        devs, stale, approval_messages, records = apply_approvals(
            info, analysis.deviations, path, current_hash=provenance.function_hash(info.node),
            base_keys=base_keys, confirmed_proposals=confirmed_proposals)
        messages.extend(approval_messages)
        meta = pattern.meta
        findings.append(Finding(
            path=path, function=info.qualname, line=info.node.lineno, provenance=kind,
            pattern=meta.key, pattern_function=analysis.pattern_function, similarity=similarity,
            deviations=devs, stale_approvals=stale, diff=analysis.diff,
            deprecated=meta.replaced_by if meta.status == "deprecated" else None,
            hash=provenance.function_hash(info.node), approvals=records,
        ))
        if meta.status == "deprecated":
            messages.append(Message(path, info.node.lineno, "warning",
                                    f"`{info.qualname}` uses deprecated {meta.key}; use {meta.replaced_by}"))
    return findings, messages


# --------------------------------------------------------------------------- #
# Files, git
# --------------------------------------------------------------------------- #


_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_diff_lines(diff_text: str) -> set[int]:
    """New-side line numbers touched by a `git diff -U0` of one file."""
    lines: set[int] = set()
    for line in diff_text.splitlines():
        m = _HUNK_RE.match(line)
        if m:
            start, count = int(m.group(1)), int(m.group(2) or 1)
            if count == 0:  # pure deletion: the line after it counts as touched
                lines.add(max(start, 1))
            lines.update(range(start, start + count))
    return lines


def changed_lines(path: Path, ref: str) -> set[int] | None:
    """Lines of `path` changed since `ref`: None = whole file (untracked), set() = unchanged."""
    folder = path.parent if path.parent.as_posix() else Path(".")

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(folder), *args], capture_output=True, text=True)

    tracked = git("ls-files", "--error-unmatch", path.name)
    if tracked.returncode != 0:
        if git("rev-parse", "--show-toplevel").returncode != 0:
            raise PcatError(f"--changed-since needs a git repository: {path}")
        return None
    proc = git("diff", "--unified=0", "--no-color", "--no-ext-diff", ref, "--", path.name)
    if proc.returncode != 0:
        raise PcatError(f"git diff against {ref!r} failed: {proc.stderr.strip()}")
    return parse_diff_lines(proc.stdout)


def lint_paths(paths: list[str], root: Path, *, include_inferred: bool, fail_on: str = "high",
               changed_since: str | None = None) -> Report:
    if fail_on not in FAIL_LEVELS:
        raise PcatError(f"--fail-on must be one of {', '.join(FAIL_LEVELS)}")
    catalog = Catalog(root)
    files, _, _ = miner.discover(paths, miner.MineSettings())
    findings: list[Finding] = []
    messages: list[Message] = []
    for f in files:
        base = Path(paths[f.input_index])
        shown = (base / f.rel).as_posix() if base.is_dir() else base.as_posix()
        data = Path(f.abs_path).read_bytes()
        if miner._is_generated(data):
            continue
        lines = None
        if changed_since:
            lines = changed_lines(Path(f.abs_path), changed_since)
            if lines is not None and not lines:
                continue
        source = data.decode("utf-8", errors="replace")
        got, msgs = lint_source(source, shown, catalog, include_inferred, lines)
        findings.extend(got)
        messages.extend(msgs)
    findings.sort(key=lambda x: (x.path, x.line, x.function))
    messages.sort(key=lambda m: (m.path, m.line, m.level, m.text))
    return Report(findings, messages, len(files), fail_on, include_inferred, changed_since)


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #


def format_text(report: Report, show_diff: bool = True) -> str:
    out = []
    for f in report.findings:
        how = "marked" if f.provenance == "marked" else f"inferred, similarity {f.similarity:.2f}, advisory"
        out.append(f"{f.path}:{f.line}: {f.function} <- {f.pattern} {f.pattern_function} ({how})")
        if not f.deviations:
            out.append("  no deviations")
        failing = {id(d) for d in f.failing(report.fail_on)}
        for d in f.deviations:
            if d["approved"]:
                tag = f" [approved ({d['approval_state']}): {d['approval']}]"
            elif d.get("approval_state") == "proposed":
                tag = f" [proposed approval, needs confirmation: {d['approval']}]" + (
                    " [fails]" if id(d) in failing else "")
            else:
                tag = " [fails]" if id(d) in failing else ""
            out.append(f"  {f.path}:{d['line']}: {d['code']} {d['severity']} #{d.get('hash') or '????????'}: "
                       f"{d['message']}{tag}")
        if show_diff and f.diff and any(not d["approved"] and d["severity"] != "low" for d in f.deviations):
            out.extend("    " + line for line in f.diff.rstrip("\n").splitlines())
    for m in report.messages:
        out.append(f"{m.path}:{m.line}: {m.level}: {m.text}")
    if report.approvals and report.base_ref is None:
        out.append("note: no base ref: approvals treated as confirmed (use --changed-since to tell "
                   "confirmed approvals from proposed ones)")
    elif report.proposals:
        out.append(f"note: {len(report.proposals)} proposed approval(s) since {report.base_ref} approve "
                   "nothing until confirmed in the pull request (see `pcat approvals check`)")
    s = report.to_dict()["summary"]
    dev = s["deviations"]
    out.append(f"{s['functions']} function(s) checked ({s['marked']} marked, {s['inferred']} inferred) in "
               f"{report.files} file(s); deviations: {dev['high']} high, {dev['medium']} medium, "
               f"{dev['low']} low; {s['failing']} failing (--fail-on {report.fail_on})")
    return "\n".join(out) + "\n"


def _gh_escape(text: str, prop: bool = False) -> str:
    text = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    if prop:
        text = text.replace(":", "%3A").replace(",", "%2C")
    return text


def format_github(report: Report) -> str:
    """GitHub Actions workflow commands: errors for failing deviations, warnings otherwise."""
    out = []
    for f in report.findings:
        failing = {id(d) for d in f.failing(report.fail_on)}
        for d in f.deviations:
            if d["approved"]:
                level = "notice"
                text = f"{d['message']} (approved, {d['approval_state']}: {d['approval']})"
            else:
                level = "error" if id(d) in failing else "warning"
                text = d["message"] + ("" if f.provenance != "inferred" else " (inferred provenance; advisory)")
                if d.get("approval_state") == "proposed":
                    text += f" (proposed approval awaiting confirmation: {d['approval']})"
            text += f" [hash #{d.get('hash') or '????????'}]"
            title = f"{d['code']} {d['title']} ({d['severity']}) - {f.pattern}"
            out.append(f"::{level} file={_gh_escape(f.path, True)},line={d['line']},"
                       f"title={_gh_escape(title, True)}::{_gh_escape(text)}")
    for m in report.messages:
        out.append(f"::{m.level} file={_gh_escape(m.path, True)},line={m.line},title=pcat lint::{_gh_escape(m.text)}")
    return "\n".join(out) + ("\n" if out else "")
