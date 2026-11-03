"""Evaluation logic for v3 (retrieval and end-to-end). Driven by scripts/mcp_eval.py.

Pure functions over plain data so they can be unit-tested on small fixtures;
no network or `claude -p` calls happen here.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Sequence
from pathlib import Path
from statistics import median

import yaml

HELDOUT_PROMPT = (
    "Here is a situation a software developer is in:\n\n{need}\n\n"
    "Write the request this developer would type to an AI coding assistant to get the code "
    "written for their Python project, in their own words, in one or two sentences. Reply "
    "with only the request text: no quotes, no preamble, no explanation."
)


# --------------------------------------------------------------------------- #
# Request sets
# --------------------------------------------------------------------------- #


def cataloged_tasks(root: Path) -> dict[str, str]:
    """task -> pattern id, for tasks the owner did not defer."""
    choices = yaml.safe_load((root / "docs/catalog-review/choices.yaml").read_text())["choices"]
    return {t: c["pattern_id"] for t, c in choices.items() if c["variant"] != "defer"}


def dev_set(root: Path) -> list[dict]:
    """35 paraphrases of the cataloged v2.1 tasks + the hand-written negatives."""
    import json

    tasks = yaml.safe_load((root / "experiments/variance/tasks.yaml").read_text())["tasks"]
    items = []
    for task, pattern_id in cataloged_tasks(root).items():
        for paraphrase in tasks[task]["paraphrases"]:
            items.append({"task": task, "request": " ".join(paraphrase.split()), "expected": pattern_id})
    negatives = json.loads((root / "experiments/mcp/dev_negatives.json").read_text())["requests"]
    items += [{"task": None, "request": r, "expected": None} for r in negatives]
    return items


def clean_request(text: str) -> str:
    """The request a generator wrote: first paragraph, without quotes or a label."""
    text = text.strip()
    text = re.sub(r"^\s*(request|prompt)\s*:\s*", "", text, flags=re.IGNORECASE)
    first = re.split(r"\n\s*\n", text, maxsplit=1)[0]
    first = " ".join(first.split())
    for quote in ('"', "'", "“", "”", "`"):
        first = first.strip(quote)
    return first.strip()


# --------------------------------------------------------------------------- #
# Retrieval metrics and threshold calibration
# --------------------------------------------------------------------------- #


def _top(ranked: Sequence[tuple[str, float]], threshold: float) -> list[str]:
    return [pid for pid, score in ranked if score >= threshold]


def retrieval_metrics(items: list[dict], threshold: float) -> dict:
    """Metrics for items with `expected` (id or None) and `ranked` [(id, score), ...].

    top1: the first result above the threshold is the expected pattern.
    top3: the expected pattern is among the first three results above the threshold.
    false_match: a negative gets any result above the threshold.
    The *_ranked variants ignore the threshold (pure ranking quality).
    """
    positives = [i for i in items if i["expected"]]
    negatives = [i for i in items if not i["expected"]]

    def rate(n: int, d: int) -> float:
        return round(n / d, 4) if d else 0.0

    top1 = sum(_top(i["ranked"], threshold)[:1] == [i["expected"]] for i in positives)
    top3 = sum(i["expected"] in _top(i["ranked"], threshold)[:3] for i in positives)
    top1_ranked = sum([p for p, _ in i["ranked"]][:1] == [i["expected"]] for i in positives)
    false = sum(bool(_top(i["ranked"], threshold)) for i in negatives)
    per_task: dict[str, dict] = {}
    for i in positives:
        row = per_task.setdefault(i["task"], {"n": 0, "top1": 0, "top3": 0, "misses": []})
        row["n"] += 1
        hits = _top(i["ranked"], threshold)
        row["top1"] += hits[:1] == [i["expected"]]
        row["top3"] += i["expected"] in hits[:3]
        if hits[:1] != [i["expected"]]:
            best = i["ranked"][0] if i["ranked"] else (None, 0.0)
            row["misses"].append({"request": i["request"], "got": hits[:1] or None,
                                  "best": [best[0], round(best[1], 3)]})
    return {
        "threshold": threshold,
        "positives": len(positives),
        "negatives": len(negatives),
        "top1": rate(top1, len(positives)),
        "top3": rate(top3, len(positives)),
        "top1_ignoring_threshold": rate(top1_ranked, len(positives)),
        "false_match_rate": rate(false, len(negatives)),
        "false_matches": [
            {"request": i["request"], "got": _top(i["ranked"], threshold)[0],
             "score": round(i["ranked"][0][1], 3)}
            for i in negatives if _top(i["ranked"], threshold)
        ],
        "per_task": dict(sorted(per_task.items())),
    }


def calibrate_threshold(items: list[dict]) -> tuple[float, list[dict]]:
    """Pick the threshold that maximises development accuracy.

    Accuracy counts a positive as correct when its top-1 result is right and
    scores at or above the threshold, and a negative as correct when its best
    score is below it. Candidates are midpoints between adjacent distinct top
    scores; among equally good candidates the median one is chosen (the middle
    of the best range), rounded to 2 decimals.
    """
    tops = sorted({round(i["ranked"][0][1], 6) for i in items if i["ranked"]})
    candidates = [0.0] + [round((a + b) / 2, 6) for a, b in zip(tops, tops[1:])] + [
        (tops[-1] + 1.0) if tops else 1.0]

    def accuracy(t: float) -> float:
        correct = 0
        for i in items:
            best = i["ranked"][0] if i["ranked"] else None
            if i["expected"]:
                correct += bool(best and best[0] == i["expected"] and best[1] >= t)
            else:
                correct += not (best and best[1] >= t)
        return correct / len(items)

    table = [{"threshold": t, "accuracy": round(accuracy(t), 4)} for t in candidates]
    best = max(r["accuracy"] for r in table)
    winners = [r["threshold"] for r in table if r["accuracy"] == best]
    return round(median(winners), 2), table


# --------------------------------------------------------------------------- #
# End-to-end scoring (Part E)
# --------------------------------------------------------------------------- #


def tool_calls(log_lines: list[dict]) -> dict[str, list[dict]]:
    calls: dict[str, list[dict]] = {"search_patterns": [], "get_pattern": [], "check_code": []}
    for line in log_lines:
        calls.setdefault(line["tool"], []).append(line)
    return calls


def import_roots(code: str) -> set[str]:
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return set()
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            roots.add(node.module.split(".")[0])
    return roots


# Requirement distribution name -> top-level import name, for the catalog's requires.
DISTRIBUTION_IMPORTS = {"pyjwt": "jwt", "requests": "requests", "sqlalchemy": "sqlalchemy"}


def library_agreement(code: str, requires: list[str]) -> bool:
    """True if the code imports every library the pattern requires (stdlib-only: imports none
    of the catalog's third-party libraries)."""
    roots = import_roots(code)
    wanted = {DISTRIBUTION_IMPORTS.get(re.match(r"[A-Za-z0-9._-]+", r).group(0).lower(), r)
              for r in requires}
    if wanted:
        return wanted <= roots
    return not (roots & set(DISTRIBUTION_IMPORTS.values()))


def pattern_match(check: dict, pattern_id: str, functions: list[str]) -> dict:
    """From a check_code-style result: does the code contain the pattern's functions?

    `shape` is True when every listed function (entry point and exports) is
    present as covered or near for this pattern; `exact` when all are covered.
    """
    found: dict[str, str] = {}
    for f in check.get("functions", []):
        if f["pattern"] == pattern_id and f["pattern_function"] in functions:
            status = f["status"]
            prev = found.get(f["pattern_function"])
            if prev != "covered":
                found[f["pattern_function"]] = status
    shape = all(fn in found for fn in functions)
    exact = shape and all(found[fn] == "covered" for fn in functions)
    return {"shape": shape, "exact": exact, "found": dict(sorted(found.items()))}
