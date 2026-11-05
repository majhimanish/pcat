"""v5.2 Part E: derivation features, inference variants, the labeled-set split."""

from __future__ import annotations

import ast

from conftest import REPO_ROOT
from pcat import catalog as cat
from pcat import derivation, provenance

LNBITS = REPO_ROOT / "experiments" / "v5" / "catalogs" / "lnbits"
PATTERNS = {p.meta.id: p for p in cat.load_catalog(LNBITS) if p.meta and p.meta.status == "active"}
REFS = provenance.references(LNBITS)


def feats(code: str, name: str, label=None):
    tree = ast.parse(code)
    node = next(n for n in tree.body if getattr(n, "name", None) == name)
    return derivation.features(tree, node, "lnbits.helpers", REFS, PATTERNS, label)


GOOD = "import re\n\n\ndef is_valid_handle(h: str) -> bool:\n    return re.fullmatch(r\"[a-z]{2,20}\", h) is not None\n"


def test_features_of_a_derived_function():
    f = feats(GOOD, "is_valid_handle", "validators.regex_match")
    assert f["best_pattern"] == "validators.regex_match" and f["best_similarity"] >= 0.85
    assert f["label_similarity"] == f["best_similarity"]
    assert f["call_overlap"] == 1.0 and f["import_overlap"] == 1.0 and f["touches_guarded"]


def test_copied_flaw_does_not_touch_the_guarded_name():
    f = feats(GOOD.replace("re.fullmatch", "re.match"), "is_valid_handle")
    assert f["best_pattern"] == "validators.regex_match" and not f["touches_guarded"]
    assert f["call_overlap"] == 0.0  # re.match is not the pattern's re.fullmatch


def item(i, label, best, sim, pattern=None, group=None, **extra):
    f = {"has_shape": True, "best_pattern": best, "best_similarity": sim, "call_overlap": 1.0,
         "import_overlap": 1.0, "touches_guarded": True, **extra}
    return derivation.Item(f"f{i}", "a", "s", group or f"a/{pattern or best}", label, pattern, f)


def test_evaluate_counts_a_wrong_pattern_as_a_false_positive():
    items = [item(1, True, "p", 0.9, "p"), item(2, True, "q", 0.9, "p"), item(3, False, "p", 0.9),
             item(4, False, "p", 0.3), item(5, True, "p", 0.3, "p")]
    r = derivation.evaluate(items, derivation.variants()["sim>=0.56"])
    assert (r["tp"], r["fp"], r["fn"], r["tn"]) == (1, 2, 2, 1)
    assert r["precision"] == 0.333 and r["recall"] == 0.333


def test_split_never_shares_a_group_or_a_function():
    items = [item(i, i % 2 == 0, f"p{i % 7}", 0.8, f"p{i % 7}" if i % 2 == 0 else None) for i in range(60)]
    halves = derivation.split(items)
    assert halves["calibration"] and halves["held_out"]
    groups = [{i.group for i in h} for h in halves.values()]
    ids = [{i.id for i in h} for h in halves.values()]
    assert not groups[0] & groups[1] and not ids[0] & ids[1]
    assert derivation.split(items) == halves  # deterministic


def test_choose_prefers_precision_with_enough_recall():
    items = [item(1, True, "p", 0.97, "p"), item(2, True, "p", 0.8, "p"), item(3, False, "q", 0.8),
             item(4, False, "q", 0.6)]
    name, scored = derivation.choose(items)
    assert scored[name]["precision"] == 1.0 and scored[name]["recall"] >= 0.5
    assert scored["sim>=0.56"]["precision"] == 0.5
