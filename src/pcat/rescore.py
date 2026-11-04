"""v5.1 re-scoring and survey helpers (Parts E and F). Standard library only.

Pure functions over the JSON that `scripts/v5_1.py` writes: which files the
survey lints, run-level comparisons between two linter versions, and summary
tables. Nothing here generates code or calls an agent.
"""

from __future__ import annotations

import ast
import random
from collections import Counter
from pathlib import Path

SEVERITIES = ("high", "medium", "low")
SURVEY_EXCLUDED_DIRS = {"tests", "test", "testing", "docs", "doc", "migrations", "alembic", "node_modules",
                        "__pycache__", ".git", ".venv", "venv", "build", "dist"}


def survey_files(app_dir: Path) -> list[str]:
    """App source files, relative and sorted: no tests, docs or migrations."""
    out = []
    for path in sorted(Path(app_dir).rglob("*.py")):
        rel = path.relative_to(app_dir)
        parts = rel.parts
        if any(p in SURVEY_EXCLUDED_DIRS or p.startswith(".") for p in parts[:-1]):
            continue
        name = parts[-1]
        if name.startswith("test_") or name.endswith("_test.py") or name in ("conftest.py", "tests.py"):
            continue
        out.append(rel.as_posix())
    return out


def count_functions(app_dir: Path, files: list[str]) -> int:
    """Functions the linter considers (every def, methods included), in `files`."""
    from pcat import provenance

    total = 0
    for rel in files:
        source = (Path(app_dir) / rel).read_text(encoding="utf-8", errors="replace")
        try:
            total += len(provenance.functions(source, ast.parse(source)))
        except (SyntaxError, ValueError):
            continue
    return total


def deviation_counts(findings: list[dict]) -> dict:
    by_code: dict[str, dict[str, int]] = {}
    sev = Counter()
    for f in findings:
        for d in f["deviations"]:
            by_code.setdefault(d["code"], Counter())[d["severity"]] += 1
            sev[d["severity"]] += 1
    return {"by_severity": {s: sev.get(s, 0) for s in SEVERITIES},
            "by_code": {c: {s: v.get(s, 0) for s in SEVERITIES} for c, v in sorted(by_code.items())}}


def survey_summary(report: dict) -> dict:
    findings = report["findings"]
    patterns = Counter(f["pattern"] for f in findings)
    return {"inferred_derived": sum(f["provenance"] == "inferred" for f in findings),
            "marked": sum(f["provenance"] == "marked" for f in findings),
            "functions_with_medium_or_high": sum(any(d["severity"] in ("high", "medium") for d in f["deviations"])
                                                 for f in findings),
            "by_pattern": dict(sorted(patterns.items())), **deviation_counts(findings)}


def medium_high(findings: list[dict]) -> list[dict]:
    """Every medium/high deviation as a flat item (path, function, pattern, code, severity, message)."""
    out = []
    for f in findings:
        for d in f["deviations"]:
            if d["severity"] in ("high", "medium"):
                out.append({"path": f["path"], "function": f["function"], "line": d.get("line") or f["line"],
                            "pattern": f["pattern"], "similarity": f.get("similarity"), "code": d["code"],
                            "severity": d["severity"], "message": d["message"]})
    return sorted(out, key=lambda x: (x["path"], x["line"], x["function"], x["code"], x["message"]))


def sample(items: list[dict], n: int, seed: str) -> list[dict]:
    """All items, or a reproducible random sample of `n` (sorted back into file order)."""
    if len(items) <= n:
        return list(items)
    rng = random.Random(seed)
    picked = sorted(rng.sample(range(len(items)), n))
    return [items[i] for i in picked]


def item_key(item: dict) -> str:
    return f"{item['path']}::{item['function']}::{item['code']}::{item['message']}"


# --------------------------------------------------------------------------- #
# v5 end-to-end: old vs new linter
# --------------------------------------------------------------------------- #


def _run_key(r: dict) -> tuple:
    return (r["app"], r["task"], r["condition"], r["sample"])


def _codes(lint: dict, severity: str | None = None) -> list[str]:
    return sorted({d["code"] for f in lint["findings"] for d in f["deviations"]
                   if severity is None or d["severity"] == severity})


def _failing_items(lint: dict) -> list[str]:
    out = []
    for f in lint["findings"]:
        if f["provenance"] not in ("marked", "marker-removed"):
            continue
        for d in f["deviations"]:
            if d["severity"] == "high" and not d.get("approved") \
                    and (f["provenance"] == "marked" or d["code"] == "PC111"):
                out.append(f"{f['function']}: {d['code']} {d['message']}")
    return out


def compare_e2e(old_runs: list[dict], new_runs: list[dict]) -> dict:
    old = {_run_key(r): r for r in old_runs}
    new = {_run_key(r): r for r in new_runs}
    keys = sorted(old)
    if set(old) != set(new):
        raise ValueError("the two re-scorings cover different runs")
    tables: dict = {}
    for label, runs in (("old", old), ("new", new)):
        for cond in ("baseline", "pcat"):
            rows = [runs[k] for k in keys if k[2] == cond]
            findings = [f for r in rows for f in r["lint"]["findings"]]
            tables.setdefault(label, {})[cond] = {
                "runs": len(rows), "would_fail_ci": sum(r["lint"]["failed"] for r in rows),
                **deviation_counts(findings),
            }
    flips = []
    changed = []
    for k in keys:
        o, n = old[k]["lint"], new[k]["lint"]
        item = {"app": k[0], "task": k[1], "condition": k[2], "sample": k[3]}
        if o["failed"] != n["failed"]:
            flips.append({**item, "old_failed": o["failed"], "new_failed": n["failed"],
                          "old_failing": _failing_items(o), "new_failing": _failing_items(n)})
        if o["deviations"] != n["deviations"] or _codes(o) != _codes(n):
            changed.append({**item, "old": o["deviations"], "new": n["deviations"],
                            "old_high_codes": _codes(o, "high"), "new_high_codes": _codes(n, "high"),
                            "removed": _diff_messages(o, n), "added": _diff_messages(n, o)})
    return {"tables": tables, "flips": flips, "changed_runs": changed}


def _diff_messages(a: dict, b: dict) -> list[str]:
    def msgs(lint):
        return Counter(f"{f['function']}: {d['code']} {d['severity']}: {d['message']}"
                       for f in lint["findings"] for d in f["deviations"])
    return sorted((msgs(a) - msgs(b)).elements())


def e2e_markdown(result: dict) -> str:
    lines = ["| Condition | Linter | Would fail CI | High | Medium | Low |", "|---|---|---|---|---|---|"]
    for cond in ("baseline", "pcat"):
        for label in ("old", "new"):
            t = result["tables"][label][cond]
            s = t["by_severity"]
            lines.append(f"| {cond} | {label} | {t['would_fail_ci']}/{t['runs']} | {s['high']} | "
                         f"{s['medium']} | {s['low']} |")
    lines.append("")
    lines.append(f"Flipped CI outcome: {len(result['flips'])}; runs whose deviations changed: "
                 f"{len(result['changed_runs'])}")
    for f in result["flips"]:
        lines.append(f"- {f['app']}/{f['task']}/{f['condition']}/{f['sample']}: "
                     f"{'fail' if f['old_failed'] else 'pass'} -> {'fail' if f['new_failed'] else 'pass'}")
    return "\n".join(lines)
