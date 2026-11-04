"""v5.1 Part D: guard review — `match: any` guards and PC102 for a changed exception."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from conftest import REPO_ROOT
from pcat import codeunit, deviation, guards, lint
from pcat.schema import Guard

CTFD = REPO_ROOT / "experiments" / "v5" / "catalogs" / "ctfd"
RUNS = REPO_ROOT / "experiments" / "v5" / "e2e" / "ctfd" / "ctfd_reset_token" / "pcat"

SOURCE = "class A(Exception):\n    pass\n\n\nclass B(Exception):\n    pass\n\n\n" \
         "def f(x):\n    if x is None:\n        raise {}\n    return x\n"


def results(exc: str, **guard):
    unit = codeunit.build_unit_from_source(SOURCE.format(exc), "f")
    return guards.check(unit, [(0, Guard(kind="must_raise", **guard))])


def test_match_any_holds_when_one_name_is_present():
    for exc in ("A", "B"):
        [r] = results(exc, names=["A", "B"], match="any")
        assert r.ok and r.item == "A | B"
    [r] = results("ValueError", names=["A", "B"], match="any")
    assert not r.ok and "no longer can raise any of `A`, `B`" in r.message
    assert [r.ok for r in results("B", names=["A", "B"])] == [False, True]  # default: each name


@pytest.mark.parametrize("guard, error", [
    (dict(kind="must_not_call", names=["a", "b"], match="any"), "applies to"),
    (dict(kind="must_raise", names=["a"], match="any"), "at least two"),
    (dict(kind="max_value", target="x", value=1, match="any"), "applies to"),
])
def test_match_any_is_validated(guard, error):
    with pytest.raises(ValidationError, match=error):
        Guard(**guard)


def test_pc102_changed_exception_is_medium_not_removed():
    pattern = SOURCE.format("A")
    pu = codeunit.build_unit_from_source(pattern, "f")
    swapped = deviation.analyze(pu, codeunit.build_unit_from_source(SOURCE.format("B"), "f"),
                                pattern_key="x.y@v1", pattern_function="f")
    [d] = [d for d in swapped.deviations if d.code == "PC102"]
    assert d.severity == "medium" and "raises `B` instead of the pattern's `A`" in d.message
    assert "if x is None" in d.message
    removed = deviation.analyze(pu, codeunit.build_unit_from_source(
        "def f(x):\n    return x\n", "f"), pattern_key="x.y@v1", pattern_function="f")
    assert [(d.code, d.severity) for d in removed.deviations if d.code == "PC102"] == [("PC102", "high")]


@pytest.mark.parametrize("sample", [2, 3])
def test_ctfd_reset_token_runs_are_reviewed_not_blocked(tmp_path, sample):
    """v5 pcat runs 2 and 3 raised the sibling's reset exception: the guard now accepts it."""
    diff = (RUNS / f"sample_{sample:02d}.diff").read_text()
    body = [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    code = "\n".join(body)
    assert "UserResetPasswordTokenInvalidException" in code
    pkg = tmp_path / "CTFd" / "utils" / "security"
    pkg.mkdir(parents=True)
    for d in (tmp_path / "CTFd", tmp_path / "CTFd" / "utils", pkg):
        (d / "__init__.py").write_text("")
    imports = ("import os\nfrom CTFd.cache import cache\nfrom CTFd.exceptions.email import (\n"
               "    UserConfirmTokenInvalidException,\n    UserResetPasswordTokenInvalidException,\n)\n"
               "from CTFd.utils.encoding import hexencode\n\n\n")
    (pkg / "email.py").write_text(imports + code + "\n")
    report = lint.lint_paths([str(pkg / "email.py")], CTFD, include_inferred=True)
    devs = [(f.function, d["code"], d["severity"]) for f in report.findings for d in f.deviations]
    verify = [d for d in devs if d[0] == "verify_reset_password_token"]
    assert ("verify_reset_password_token", "PC102", "medium") in verify
    assert not any(c == "PC100" for _, c, _ in verify)
