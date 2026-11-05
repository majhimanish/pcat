"""Is function F derived from pattern P? Features, variants and evaluation (v5.2 Part E).

Inference (`provenance.infer`) picks the most similar catalog function by shape and calls
the code derived when the similarity is at least `INFERENCE_THRESHOLD`. v5.1 showed that on
application code most of those calls are wrong. This module computes a few cheap features
for a (function, candidate pattern) pair, defines inference variants over them, splits a
labeled set into halves that share no functions, and reports precision and recall.
Standard library only; nothing here changes the default inference.
"""

from __future__ import annotations

import ast
import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from pcat import codeunit, deviation, guards, provenance
from pcat.codeunit import name_key


@dataclass(frozen=True)
class Item:
    """One labeled function. `label`: derived from `label_pattern` (positives) or from no
    pattern (negatives: `label_pattern` is None). `group` decides the split half."""
    id: str
    app: str
    source: str  # where the label comes from
    group: str
    label: bool
    label_pattern: str | None
    features: dict


def _calls(unit) -> set[str]:
    return {f.key for f in codeunit.calls(unit) if not f.key.startswith(".")}


def _import_roots(unit) -> set[str]:
    return {o.split(".")[0] for o in unit.imports.values() if not o.startswith(".")}


def _guard_names(meta, function: str) -> list[str]:
    out = []
    for _, g in guards.applicable(meta, function):
        out += [n for n in g.names] if g.names else [g.target]
    return out


def _touches(unit, names: list[str], node) -> bool:
    resolved = [f.dotted for f in codeunit.calls(unit)]
    resolved += [k for _, k, _ in codeunit.raises(unit)]
    resolved += [t for _, ts, _ in codeunit.handlers(unit) for t in ts]
    params = {a.arg for a in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]}
    for name in names:
        if name in params or name in unit.constants:
            return True
        if any(codeunit.target_matches(name, r, unit) for r in resolved):
            return True
    return False


def features(tree: ast.Module, node, module: str | None, refs: list[provenance.Reference],
             patterns: dict[str, object], label_pattern: str | None = None) -> dict:
    """Features of `node` against its most similar catalog function (and, when given, against
    the label pattern's best function). `patterns`: pattern id -> catalog Pattern."""
    text = provenance.shape_text(node)
    if text is None:
        return {"has_shape": False}
    ranked = provenance.rank(text, refs)
    sim, best = ranked[0]
    out = {"has_shape": True, "best_pattern": best.pattern_id, "best_function": best.function,
           "best_similarity": sim,
           "margin": round(sim - next((s for s, r in ranked if r.pattern_id != best.pattern_id), 0.0), 4)}
    if label_pattern is not None:
        out["label_similarity"] = max((s for s, r in ranked if r.pattern_id == label_pattern), default=0.0)
    uu = codeunit.build_unit(tree, node, module)
    pattern = patterns[best.pattern_id]
    pu = codeunit.build_unit_from_source(pattern.impl_path.read_text(encoding="utf-8"), best.function)
    pu, uu, _ = deviation.bind(pu, uu)
    p_calls, u_calls = _calls(pu), _calls(uu)
    out["call_overlap"] = round(len(p_calls & u_calls) / len(p_calls), 4) if p_calls else 1.0
    p_roots, u_roots = _import_roots(pu), _import_roots(uu)
    out["import_overlap"] = round(len(p_roots & u_roots) / len(p_roots), 4) if p_roots else 1.0
    names = _guard_names(pattern.meta, best.function)
    out["has_guards"] = bool(names)
    out["touches_guarded"] = _touches(uu, names, node) if names else False
    out["lines"] = node.end_lineno - node.lineno + 1
    return out


# --------------------------------------------------------------------------- #
# Variants
# --------------------------------------------------------------------------- #

Predicate = Callable[[dict], bool]


def _sim(t: float) -> Predicate:
    return lambda f: f.get("has_shape", False) and f["best_similarity"] >= t


def variants() -> dict[str, Predicate]:
    """A small fixed family: the default, stricter thresholds, and structural requirements."""
    out: dict[str, Predicate] = {}
    for t in (0.56, 0.65, 0.75, 0.85, 0.9, 0.95):
        out[f"sim>={t}"] = _sim(t)
    for t in (0.56, 0.75, 0.85):
        base = _sim(t)
        out[f"sim>={t}+calls>=0.5"] = lambda f, b=base: b(f) and f["call_overlap"] >= 0.5
        out[f"sim>={t}+calls>=0.8"] = lambda f, b=base: b(f) and f["call_overlap"] >= 0.8
        out[f"sim>={t}+imports"] = lambda f, b=base: b(f) and f["import_overlap"] >= 1.0
        out[f"sim>={t}+guarded"] = lambda f, b=base: b(f) and f["touches_guarded"]
        out[f"sim>={t}+imports+calls>=0.5"] = lambda f, b=base: (b(f) and f["import_overlap"] >= 1.0
                                                                and f["call_overlap"] >= 0.5)
    return out


def predict(item: Item, predicate: Predicate) -> bool:
    """Predicted "derived from `label_pattern`" (positives) or "derived from something"
    (negatives): the variant accepts, and for a positive the accepted pattern is the right one."""
    f = item.features
    if not predicate(f):
        return False
    return True if item.label_pattern is None else f["best_pattern"] == item.label_pattern


def evaluate(items: list[Item], predicate: Predicate) -> dict:
    tp = fp = fn = tn = 0
    for item in items:
        accepted = predicate(item.features) if item.features.get("has_shape") else False
        right = accepted and (item.label_pattern is None or item.features["best_pattern"] == item.label_pattern)
        if item.label:
            if right:
                tp += 1
            else:
                fn += 1
                if accepted:
                    fp += 1  # accepted, but attributed to the wrong pattern
        elif accepted:
            fp += 1
        else:
            tn += 1
    precision = round(tp / (tp + fp), 3) if tp + fp else None
    recall = round(tp / (tp + fn), 3) if tp + fn else None
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall}


# --------------------------------------------------------------------------- #
# Split
# --------------------------------------------------------------------------- #


def half_of(group: str) -> str:
    """"calibration" or "held_out", fixed by a hash of the group (an app/pattern pair)."""
    return "calibration" if int(hashlib.sha256(group.encode()).hexdigest(), 16) % 2 == 0 else "held_out"


def split(items: list[Item]) -> dict[str, list[Item]]:
    out: dict[str, list[Item]] = {"calibration": [], "held_out": []}
    for item in items:
        out[half_of(item.group)].append(item)
    return out


def choose(items: list[Item], min_recall: float = 0.5) -> tuple[str, dict]:
    """Best variant on `items` by precision, among those with at least `min_recall`
    (ties: higher recall, then name); if none reaches it, the best by precision."""
    scored = {name: evaluate(items, p) for name, p in variants().items()}
    eligible = {n: s for n, s in scored.items() if s["precision"] is not None
                and (s["recall"] or 0) >= min_recall}
    pool = eligible or {n: s for n, s in scored.items() if s["precision"] is not None}
    name = sorted(pool, key=lambda n: (-pool[n]["precision"], -(pool[n]["recall"] or 0), n))[0]
    return name, scored
