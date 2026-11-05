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
            pairs.append((provenance.similarity.similarity(text, ref.shape_text), qualname, ref))
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


# --------------------------------------------------------------------------- #
# Replay and feedback-run scoring
# --------------------------------------------------------------------------- #

SEVERITIES = ("none", "low", "medium", "high")


def fetched_patterns(tool_calls: list[dict]) -> list[str]:
    """Pattern ids the agent fetched with get_pattern, in call order (without @vN)."""
    out = []
    for call in tool_calls:
        if call["tool"] == "get_pattern":
            got = (call.get("result") or {}).get("id") or call["arguments"].get("id")
            if got and "error" not in (call.get("result") or {}):
                pid = got.split("@")[0]
                if pid not in out:
                    out.append(pid)
    return out


def worst(analyses: list[dict], approved: bool = False) -> str:
    """Highest severity among deviations (unapproved only, unless approved=True)."""
    rank = 0
    for a in analyses:
        for d in a["deviations"]:
            if approved or not d["approved"]:
                rank = max(rank, SEVERITIES.index(d["severity"]))
    return SEVERITIES[rank]


def codes(analyses: list[dict]) -> list[str]:
    return sorted({d["code"] for a in analyses for d in a["deviations"]})


def high_codes(analyses: list[dict]) -> list[str]:
    return sorted({d["code"] for a in analyses for d in a["deviations"] if d["severity"] == "high"})


def confusion(rows: list[dict]) -> dict:
    """outcome -> worst severity -> count."""
    table: dict[str, dict[str, int]] = {}
    for r in rows:
        table.setdefault(r["outcome"], {s: 0 for s in SEVERITIES})[r["worst"]] += 1
    return dict(sorted(table.items()))


def replay_checks(rows: list[dict]) -> dict:
    """The spec's expectations for the v3 replay, evaluated on scored rows."""
    exact = [r for r in rows if r["outcome"] == "matched"]
    misses = [r for r in rows if r["outcome"] != "matched"]
    precision = [r for r in exact if set(r["codes"]) - {"PC109"}]
    http = [r for r in misses if r["task"] == "http_retry"]
    pag = [r for r in misses if r["task"] == "paginate_query"]
    csv_switched = [r for r in misses if r["task"] == "csv_import" and r["switched_library"]]
    return {
        "exact_matches": len(exact),
        "exact_with_deviation_other_than_PC109": len(precision),
        "exact_flagged_above_low": sum(r["worst"] in ("medium", "high") for r in exact),
        "misses": len(misses),
        "misses_with_a_deviation": sum(bool(r["codes"]) for r in misses),
        "http_misses": len(http),
        "http_misses_high_PC100_or_PC101": sum(bool({"PC100", "PC101"} & set(r["high_codes"])) for r in http),
        "pagination_misses": len(pag),
        "pagination_misses_with_PC106": sum("PC106" in r["codes"] for r in pag),
        "csv_misses_switched_library": len(csv_switched),
        "csv_switched_with_PC103": sum("PC103" in r["codes"] for r in csv_switched),
    }


CENSUS_STATES = ("confirmable", "stale_hash", "no_hash", "invalid")


def approval_census(code: str) -> list[dict]:
    """Every `# pcat-allow` line in final code: confirmable (hash matches the function, a
    human could confirm it), stale_hash (hash of other code), no_hash (v4 format), invalid."""
    try:
        infos = provenance.functions(code)
    except (SyntaxError, ValueError):
        return []
    out = []
    for info in infos:
        current = provenance.function_hash(info.node)
        for a in info.approvals:
            if a.problem and a.code is None:
                state = "invalid"
            elif a.problem:
                state = "invalid"
            elif a.hash is None:
                state = "no_hash"
            elif a.hash != current:
                state = "stale_hash"
            else:
                state = "confirmable"
            out.append({"function": info.qualname, "code": a.code, "hash": a.hash,
                        "current_hash": current, "state": state, "reason": a.reason})
    return out


def worst_not_proposed(analyses: list[dict]) -> str:
    """Highest severity among deviations neither approved nor covered by a proposal."""
    rank = 0
    for a in analyses:
        for d in a["deviations"]:
            if not d["approved"] and d.get("approval_state") != "proposed":
                rank = max(rank, SEVERITIES.index(d["severity"]))
    return SEVERITIES[rank]
