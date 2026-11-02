"""Every check in spec section 10 has a test that triggers its failure."""

from __future__ import annotations

import shutil
import subprocess

import pytest
import yaml

from conftest import edit_yaml, pattern_dir
from pcat import canonical
from pcat import catalog as cat

ITER = "search.binary_search.iterative"
REC = "search.binary_search.recursive"


def checks(problems) -> set[str]:
    return {p.check for p in problems}


def reindex(root):
    cat.write_index(root)


def test_seed_copy_is_valid(root):
    assert cat.validate(root, run_tests=False) == []


# 1 ------------------------------------------------------------------------- #
def test_check1_unknown_key(root):
    edit_yaml(pattern_dir(root, ITER), surprise=True)
    problems = cat.validate(root, run_tests=False)
    assert "1" in checks(problems)
    assert any("surprise" in p.message for p in problems)


def test_check1_bad_types_and_missing_fields(root):
    folder = pattern_dir(root, ITER)
    text = (folder / "pattern.yaml").read_text()
    text = text.replace("version: 1", "version: one").replace("title:", "xtitle:")
    (folder / "pattern.yaml").write_text(text)
    messages = [p.message for p in cat.validate(root, run_tests=False) if p.check == "1"]
    assert any("version" in m for m in messages)
    assert any("title" in m for m in messages)


def test_check1_id_must_match_folder(root):
    edit_yaml(pattern_dir(root, ITER), id="search.binary_search.loop")
    problems = cat.validate(root, run_tests=False)
    assert any(p.check == "1" and "folder does not match" in p.message for p in problems)


def test_check1_category_must_match_id(root):
    edit_yaml(pattern_dir(root, ITER), category="sort")
    problems = cat.validate(root, run_tests=False)
    assert any(p.check == "1" and "category" in p.message for p in problems)


def test_check1_missing_pattern_yaml(root):
    (pattern_dir(root, ITER) / "pattern.yaml").unlink()
    assert "1" in checks(cat.validate(root, run_tests=False))


# 2 ------------------------------------------------------------------------- #
def test_check2_top_level_statement_rejected(root):
    impl = pattern_dir(root, ITER) / "impl.py"
    impl.write_text(impl.read_text() + "\nCACHE = dict()\n")
    problems = cat.validate(root, run_tests=False)
    assert any(p.check == "2" and "not a literal constant" in p.message for p in problems)


def test_check2_syntax_error(root):
    (pattern_dir(root, ITER) / "impl.py").write_text("def broken(:\n")
    assert "2" in checks(cat.validate(root, run_tests=False))


def test_check2_missing_impl(root):
    (pattern_dir(root, ITER) / "impl.py").unlink()
    assert "2" in checks(cat.validate(root, run_tests=False))


# 3 ------------------------------------------------------------------------- #
def test_check3_entry_point_missing(root):
    edit_yaml(pattern_dir(root, ITER), entry_point="bsearch")
    problems = cat.validate(root, run_tests=False)
    assert any(p.check == "3" and "bsearch" in p.message for p in problems)


# 4 ------------------------------------------------------------------------- #
def test_check4_editing_impl_breaks_fingerprint(root):
    impl = pattern_dir(root, ITER) / "impl.py"
    impl.write_text(impl.read_text().replace("return -1", "return None"))
    problems = cat.validate(root, run_tests=False)
    assert any(p.check == "4" and "mismatch" in p.message for p in problems)


def test_check4_comment_only_edit_keeps_fingerprint(root):
    impl = pattern_dir(root, ITER) / "impl.py"
    impl.write_text("# a new comment\n" + impl.read_text())
    assert cat.validate(root, run_tests=False) == []


def test_check4_fingerprint_not_set(root):
    edit_yaml(pattern_dir(root, ITER), fingerprint=None)
    reindex(root)
    problems = cat.validate(root, run_tests=False)
    assert any(p.check == "4" and "not set" in p.message for p in problems)


# 5 ------------------------------------------------------------------------- #
def test_check5_duplicate_fingerprint_reports_both_ids(root):
    src = pattern_dir(root, ITER)
    dst = pattern_dir(root, "search.binary_search.copy")
    shutil.copytree(src, dst)
    edit_yaml(dst, id="search.binary_search.copy", variant_of=None)
    reindex(root)
    problems = [p for p in cat.validate(root, run_tests=False) if p.check == "5"]
    assert len(problems) == 1
    assert ITER in problems[0].subject and "search.binary_search.copy" in problems[0].subject


# 6 ------------------------------------------------------------------------- #
def test_check6_variants_with_identical_behavior(root):
    behavior = yaml.safe_load((pattern_dir(root, ITER) / "pattern.yaml").read_text())["behavior"]
    edit_yaml(pattern_dir(root, REC), behavior=behavior)
    reindex(root)
    problems = [p for p in cat.validate(root, run_tests=False) if p.check == "6"]
    assert len(problems) == 1
    assert ITER in problems[0].subject and REC in problems[0].subject


# 7 ------------------------------------------------------------------------- #
def test_check7_replaced_by_must_resolve(root):
    edit_yaml(pattern_dir(root, ITER), status="deprecated", replaced_by="search.nothing_here")
    reindex(root)
    problems = cat.validate(root, run_tests=False)
    assert any(p.check == "7" and "search.nothing_here" in p.message for p in problems)


def test_check7_cannot_be_replaced_by_itself(root):
    edit_yaml(pattern_dir(root, ITER), status="deprecated", replaced_by=ITER)
    reindex(root)
    assert "7" in checks(cat.validate(root, run_tests=False))


def test_check7_deprecated_requires_replaced_by(root):
    edit_yaml(pattern_dir(root, ITER), status="deprecated")
    problems = cat.validate(root, run_tests=False)
    assert any(p.check == "1" and "replaced_by" in p.message for p in problems)


def test_new_version_flow_is_valid(root):
    """Section 9: change code via <id>@v2 and deprecate v1."""
    v1 = pattern_dir(root, ITER)
    v2 = pattern_dir(root, ITER, 2)
    shutil.copytree(v1, v2)
    impl = v2 / "impl.py"
    impl.write_text(impl.read_text().replace("if value == target:", "if target == value:"))
    edit_yaml(v2, version=2)
    pattern = cat.get_one(root, f"{ITER}@v2")
    cat.write_fingerprint(pattern, cat.analyze_pattern(pattern).fingerprint)
    edit_yaml(v1, status="deprecated", replaced_by=ITER)
    reindex(root)
    assert cat.validate(root) == []
    assert cat.get_one(root, ITER).meta.version == 2


# 8 ------------------------------------------------------------------------- #
def test_check8_failing_tests(root):
    test = pattern_dir(root, ITER) / "test_impl.py"
    test.write_text(test.read_text() + "\n\ndef test_wrong():\n    assert binary_search([1], 1) == 99\n")
    problems = cat.validate(root, [ITER])
    assert any(p.check == "8" and "1 failed" in p.message for p in problems)


def test_check8_missing_tests(root):
    (pattern_dir(root, ITER) / "test_impl.py").unlink()
    problems = cat.validate(root, run_tests=False)
    assert any(p.check == "8" and "missing" in p.message for p in problems)


def test_check8_tests_are_isolated_per_pattern(root):
    # Every pattern imports a module called `impl`; running them all must work.
    assert cat.validate(root) == []


# 9 ------------------------------------------------------------------------- #
def test_check9_idempotence_failure_detected(root, monkeypatch):
    real_render = canonical.render

    def lossy_render(text, name_map):
        return real_render(text, name_map).replace("len(", "abs(")

    monkeypatch.setattr(canonical, "render", lossy_render)
    problems = cat.validate(root, [ITER], run_tests=False)
    assert any(p.check == "9" for p in problems)


# 10 ------------------------------------------------------------------------ #
def test_check10_stale_index(root):
    edit_yaml(pattern_dir(root, ITER), title="Something else")
    problems = cat.validate(root, run_tests=False)
    assert checks(problems) == {"10"}


def test_check10_missing_index(root):
    (root / "catalog" / "index.json").unlink()
    assert checks(cat.validate(root, run_tests=False)) == {"10"}


# subset selection ---------------------------------------------------------- #
def test_validate_unknown_id(root):
    problems = cat.validate(root, ["nope.nothing"], run_tests=False)
    assert any("no such pattern" in p.message for p in problems)


def test_validate_subset_ignores_other_patterns(root):
    (pattern_dir(root, REC) / "impl.py").write_text("X = 1\n")
    assert cat.validate(root, [ITER], run_tests=False) == []
    assert cat.validate(root, [REC], run_tests=False) != []


# immutability against a git base ------------------------------------------ #
def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def git_root(root):
    _git(root, "init", "-q")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
    return root


def test_base_check_rejects_rewritten_fingerprint(git_root):
    folder = pattern_dir(git_root, ITER)
    impl = folder / "impl.py"
    impl.write_text(impl.read_text().replace("return -1", "return None"))
    pattern = cat.get_one(git_root, ITER)
    cat.write_fingerprint(pattern, cat.analyze_pattern(pattern).fingerprint)
    reindex(git_root)
    assert cat.validate(git_root, run_tests=False) == []  # self-consistent...
    problems = cat.validate(git_root, run_tests=False, base="HEAD")
    assert any(p.check == "immutable" and "fingerprint" in p.message for p in problems)


def test_base_check_rejects_removed_pattern(git_root):
    shutil.rmtree(pattern_dir(git_root, ITER))
    reindex(git_root)
    problems = cat.validate(git_root, run_tests=False, base="HEAD")
    assert any(p.check == "immutable" and "removed" in p.message for p in problems)


def test_base_check_allows_deprecation(git_root):
    edit_yaml(pattern_dir(git_root, REC), status="deprecated", replaced_by=ITER)
    reindex(git_root)
    assert cat.validate(git_root, run_tests=False, base="HEAD") == []
