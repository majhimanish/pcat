"""v3 metadata: exports, keywords, use_when, usage."""

from __future__ import annotations

import json
import subprocess

import pytest

from conftest import REPO_ROOT, edit_yaml, pattern_dir
from pcat import catalog as cat

ITER = "search.binary_search.iterative"
PBKDF2 = "auth.password.pbkdf2"


def test_every_real_pattern_has_search_metadata():
    for p in cat.load_catalog(REPO_ROOT):
        assert 5 <= len(p.meta.keywords) <= 15, p.label
        assert p.meta.use_when and p.meta.usage, p.label
    exports = {p.meta.id: p.meta.exports for p in cat.load_catalog(REPO_ROOT)}
    assert exports[PBKDF2] == ["verify_password", "needs_rehash"]
    assert exports["config.env.load_settings"] == ["parse_bool"]


def test_metadata_is_in_every_index_entry(root):
    entries = json.loads((root / "catalog" / "index.json").read_text())["patterns"]
    for entry in entries:
        assert {"requires", "exports", "keywords", "use_when", "usage"} <= set(entry)
    pbkdf2 = next(e for e in entries if e["id"] == PBKDF2)
    assert pbkdf2["exports"] == ["verify_password", "needs_rehash"] and "verify_password" in pbkdf2["usage"]


def test_missing_export_fails_check3(root):
    edit_yaml(pattern_dir(root, PBKDF2), exports=["verify_password", "check_strength"])
    cat.write_index(root)
    problems = cat.validate(root, [PBKDF2], run_tests=False)
    assert [p.check for p in problems] == ["3"] and "check_strength" in problems[0].message


@pytest.mark.parametrize("field,value,message", [
    ("keywords", ["a", "b"], "5-15 keywords"),
    ("keywords", [f"k{i}" for i in range(16)], "5-15 keywords"),
    ("keywords", ["a", "b", "c", "d", "A"], "unique"),
    ("exports", ["not valid"], "valid Python function name"),
    ("exports", ["binary_search"], "must not repeat the entry_point"),
    ("use_when", "", "at least 1 character"),
    ("usage", "", "at least 1 character"),
])
def test_invalid_metadata_rejected(root, field, value, message):
    edit_yaml(pattern_dir(root, ITER), **{field: value})
    problems = cat.validate(root, run_tests=False)  # invalid metadata: not selectable by id
    assert any(p.check == "1" and message in p.message for p in problems), problems


def test_metadata_never_changes_fingerprints(root):
    before = {p.meta.key: cat.analyze_pattern(p).fingerprint for p in cat.load_catalog(root)}
    edit_yaml(pattern_dir(root, ITER), keywords=["x1", "x2", "x3", "x4", "x5"], use_when="Other text.",
              usage="other()", exports=[])
    after = {p.meta.key: cat.analyze_pattern(p).fingerprint for p in cat.load_catalog(root)}
    stored = {p.meta.key: p.meta.fingerprint for p in cat.load_catalog(root)}
    assert before == after == stored


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


def test_metadata_only_change_passes_base_but_impl_change_does_not(root):
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "approved")
    edit_yaml(pattern_dir(root, ITER), keywords=["find", "search", "sorted", "index", "fast"],
              use_when="Changed wording.", usage="i = binary_search(xs, x)")
    cat.write_index(root)
    assert cat.validate(root, run_tests=False, base="HEAD") == []
    impl = pattern_dir(root, ITER) / "impl.py"
    impl.write_text(impl.read_text() + "\n# a comment\n")
    problems = cat.validate(root, run_tests=False, base="HEAD")
    assert any(p.check == "immutable" and "impl.py changed" in p.message for p in problems)
