"""Evaluation logic for v4 (inference calibration, replay, feedback run).

Driven by scripts/lint_eval.py. Pure functions over plain data so they can be
unit-tested on small fixtures; no `claude -p` calls happen here.
"""

from __future__ import annotations

import ast

from pcat import provenance


def sample_functions(code: str) -> list[tuple[str, ast.FunctionDef, str]]:
    """(qualname, node, shape text) of every non-trivial function in `code`."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return []
    out = []
    for info in provenance.functions(code, tree):
        try:
            mined = provenance.miner.mine_function(info.node)
        except Exception:  # noqa: BLE001 - unanalyzable function: skip
            continue
        if not mined["trivial"]:
            out.append((info.qualname, info.node, mined["shape_text"]))
    return out


def derived_functions(code: str, refs: list[provenance.Reference]) -> list[tuple[str, str]]:
    """Positive labels for a sample known to derive from the pattern of `refs`.

    For each pattern function (entry point, exports), the sample function most
    similar to it, each sample function used at most once: [(qualname, "id:function")].
    """
    funcs = sample_functions(code)
    pairs = []
    for ref in refs:
        for qualname, _, text in funcs:
            pairs.append((provenance.variance.similarity(text, ref.shape_text), qualname, ref))
    pairs.sort(key=lambda p: (-p[0], p[1], p[2].function))
    used_q: set[str] = set()
    used_r: set[str] = set()
    out = []
    for _, qualname, ref in pairs:
        if qualname in used_q or ref.function in used_r:
            continue
        used_q.add(qualname)
        used_r.add(ref.function)
        out.append((qualname, f"{ref.pattern_id}:{ref.function}"))
    return sorted(out)


def ranked_item(text: str, refs: list[provenance.Reference], expected: str | None) -> dict:
    """An item for evaluation.calibrate_threshold / retrieval_metrics: best match first."""
    sim, ref = provenance._best(text, refs)
    return {"expected": expected, "ranked": [(f"{ref.pattern_id}:{ref.function}", sim)]}


def inference_summary(items: list[dict], threshold: float) -> dict:
    """Correct / incorrect inferences at `threshold` for labeled items."""
    pos = [i for i in items if i["expected"]]
    neg = [i for i in items if not i["expected"]]
    tp = sum(1 for i in pos if i["ranked"][0][1] >= threshold and i["ranked"][0][0] == i["expected"])
    wrong_pattern = sum(1 for i in pos if i["ranked"][0][1] >= threshold and i["ranked"][0][0] != i["expected"])
    fn = len(pos) - tp - wrong_pattern
    fp = sum(1 for i in neg if i["ranked"][0][1] >= threshold)
    return {
        "threshold": threshold,
        "derived": len(pos),
        "not_derived": len(neg),
        "derived_inferred_correctly": tp,
        "derived_inferred_wrong_pattern": wrong_pattern,
        "derived_missed": fn,
        "not_derived_inferred_as_derived": fp,
        "not_derived_correct": len(neg) - fp,
    }
