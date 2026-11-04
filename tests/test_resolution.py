"""v5.1 Part A: one symbol table per code unit, used identically on the pattern and code sides."""

from __future__ import annotations

import ast
import re
import shutil
from types import SimpleNamespace

import pytest

from conftest import REPO_ROOT
from pcat import codeunit, deviation, guards, lint
from pcat.schema import Guard

LNBITS_CATALOG = REPO_ROOT / "experiments" / "v5" / "catalogs" / "lnbits"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "lnbits_mini"
V5_RUNS = REPO_ROOT / "experiments" / "v5" / "e2e" / "lnbits" / "lnbits_invoice_key" / "pcat"


def added_function(diff: str) -> str:
    """The function a v5 run added, as the `+` lines of its diff."""
    lines = [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    return "\n".join(lines).strip("\n") + "\n"


def without_marked_function(source: str) -> str:
    return source[: source.index("# pcat: auth.require_api_key@v1")]


# --------------------------------------------------------------------------- #
# The 3 LNbits false CI failures from v5 (exact reproductions of the original)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("sample", [1, 2, 3])
def test_lnbits_exact_reproductions_no_longer_fail(tmp_path, sample):
    repo = tmp_path / "repo"
    shutil.copytree(FIXTURE, repo)
    path = repo / "lnbits" / "decorators.py"
    written = added_function((V5_RUNS / f"sample_{sample:02d}.diff").read_text())
    assert "KeyChecker(" in written and written.startswith("# pcat: auth.require_api_key@v1")
    path.write_text(without_marked_function(path.read_text()) + written)
    report = lint.lint_paths([str(repo)], LNBITS_CATALOG, include_inferred=True)
    marked = [f for f in report.findings if f.provenance == "marked"]
    assert [f.function for f in marked] == ["require_invoice_key"]
    assert not report.failed
    assert all(d["code"] != "PC100" for f in report.findings for d in f.deviations)
    assert all(d["severity"] != "high" for f in report.findings for d in f.deviations)


def test_lnbits_class_resolves_to_its_module_on_both_sides():
    source = (FIXTURE / "lnbits" / "decorators.py").read_text()
    tree = ast.parse(source)
    node = next(n for n in tree.body if getattr(n, "name", None) == "require_invoice_key")
    uu = codeunit.build_unit(tree, node, "lnbits.decorators")
    pu = codeunit.build_unit_from_source(
        next(LNBITS_CATALOG.rglob("require_api_key/impl.py")).read_text(), "require_admin_key")
    call = lambda u: next(c for c in codeunit.calls(u) if c.display.endswith("KeyChecker"))  # noqa: E731
    assert call(uu).dotted == call(pu).dotted == "lnbits.decorators.KeyChecker"
    assert call(uu).display == "KeyChecker" and call(pu).display == "lnbits.decorators.KeyChecker"
    assert uu.resolution == "full" and uu.unknown == set()


def test_the_wrong_class_of_the_same_name_still_violates_the_guard():
    source = (FIXTURE / "lnbits" / "decorators.py").read_text()
    tree = ast.parse(source)
    node = next(n for n in tree.body if getattr(n, "name", None) == "require_invoice_key")
    unit = codeunit.build_unit(tree, node, "otherapp.auth")  # its own KeyChecker, not lnbits'
    [r] = guards.check(unit, [(0, Guard(kind="must_call", names=["lnbits.decorators.KeyChecker"]))])
    assert not r.ok and not r.skipped


# --------------------------------------------------------------------------- #
# Symbol table: aliases, same-file classes/functions/constants, attribute chains
# --------------------------------------------------------------------------- #


def resolve_all(source: str, name: str = "f", module: str | None = None) -> list[str]:
    unit = codeunit.build_unit_from_source(source, name, module)
    return [c.dotted for c in codeunit.calls(unit)]


def test_aliases_resolve_to_the_origin():
    src = ("import requests as rq\nfrom hmac import compare_digest as eq\nimport os.path\n"
           "def f(a, b):\n    rq.get(a)\n    eq(a, b)\n    os.path.join(a, b)\n")
    assert resolve_all(src) == ["requests.get", "hmac.compare_digest", "os.path.join"]


def test_same_file_classes_functions_and_attribute_chains():
    src = ("class Checker:\n    @classmethod\n    def build(cls):\n        return cls()\n"
           "registry = dict()\n"
           "def other():\n    return 1\n"
           "def f(x):\n    Checker(x)\n    Checker.build()\n    registry.get(x)\n    other()\n")
    assert resolve_all(src, module="pkg.mod") == [
        "pkg.mod.Checker", "pkg.mod.Checker.build", "pkg.mod.registry.get"]  # other() is a helper
    assert resolve_all(src) == ["Checker", "Checker.build", "registry.get"]  # module unknown: bare
    unit = codeunit.build_unit_from_source(src, "f", "pkg.mod")
    assert unit.helper_names == {"other"} and unit.spell("pkg.mod.Checker.build") == "Checker.build"


def test_type_checking_and_fallback_imports_are_in_the_table():
    src = ("from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from app.models import User\n"
           "try:\n    import ujson as json\nexcept ImportError:\n    import json\n"
           "def f(x):\n    User(x)\n    json.dumps(x)\n")
    unit = codeunit.build_unit_from_source(src, "f")
    assert resolve_all(src) == ["app.models.User", "json.dumps"] and unit.resolution == "full"


def test_module_for_path(tmp_path):
    (tmp_path / "pkg" / "sub").mkdir(parents=True)
    for p in ("pkg/__init__.py", "pkg/sub/__init__.py", "pkg/sub/mod.py", "script.py"):
        (tmp_path / p).write_text("")
    assert codeunit.module_for_path(tmp_path / "pkg" / "sub" / "mod.py") == "pkg.sub.mod"
    assert codeunit.module_for_path(tmp_path / "pkg" / "sub" / "__init__.py") == "pkg.sub"
    assert codeunit.module_for_path(tmp_path / "script.py") == "script"
    assert codeunit.module_for_path(tmp_path / "notes.txt") is None


# --------------------------------------------------------------------------- #
# Guard targets
# --------------------------------------------------------------------------- #


CLASS_IN_FILE = "class KeyChecker:\n    pass\n\ndef f(k):\n    return KeyChecker(k)\n"
CLASS_IMPORTED = "from lnbits.decorators import KeyChecker as KC\n\ndef f(k):\n    return KC(k)\n"


@pytest.mark.parametrize("module", [None, "lnbits.decorators", "app.x"])
def test_unqualified_target_matches_a_same_file_definition(module):
    unit = codeunit.build_unit_from_source(CLASS_IN_FILE, "f", module)
    [r] = guards.check(unit, [(0, Guard(kind="must_call", names=["KeyChecker"]))])
    assert r.ok


def test_qualified_target_matches_any_alias_and_the_defining_module():
    target = [(0, Guard(kind="must_call", names=["lnbits.decorators.KeyChecker"]))]
    assert guards.check(codeunit.build_unit_from_source(CLASS_IMPORTED, "f"), target)[0].ok
    assert guards.check(codeunit.build_unit_from_source(CLASS_IN_FILE, "f", "lnbits.decorators"), target)[0].ok
    unit = codeunit.build_unit_from_source(CLASS_IMPORTED.replace("lnbits.decorators", "other.mod"), "f")
    assert not guards.check(unit, target)[0].ok


def test_unqualified_target_also_matches_an_import_of_that_name():
    unit = codeunit.build_unit_from_source(CLASS_IMPORTED, "f")
    assert guards.check(unit, [(0, Guard(kind="must_call", names=["KeyChecker"]))])[0].ok


def test_must_not_call_is_strict_for_unqualified_targets():
    src = "import builtins_free as bf\n\ndef f(x):\n    return bf.eval(x)\n"
    unit = codeunit.build_unit_from_source(src, "f")
    assert guards.check(unit, [(0, Guard(kind="must_not_call", names=["eval"]))])[0].ok
    unit = codeunit.build_unit_from_source("def f(x):\n    return eval(x)\n", "f")
    assert not guards.check(unit, [(0, Guard(kind="must_not_call", names=["eval"]))])[0].ok


def test_same_file_exception_satisfies_must_raise_and_must_catch():
    src = ("class TokenInvalid(Exception):\n    pass\n\n"
           "def f(t):\n    try:\n        return g(t)\n    except TokenInvalid:\n        raise TokenInvalid()\n")
    for module in (None, "ctfd.utils"):
        unit = codeunit.build_unit_from_source(src, "f", module)
        res = guards.check(unit, [(0, Guard(kind="must_raise", names=["TokenInvalid"])),
                                  (1, Guard(kind="must_catch", names=["ctfd.utils.TokenInvalid"]))])
        assert [r.ok for r in res] == [True, module is not None]


# --------------------------------------------------------------------------- #
# Identical results on the pattern side and the code side
# --------------------------------------------------------------------------- #


PATTERN_IMPORTS = '''\
from fastapi import Request
from lnbits.decorators import KeyChecker, helper_check


async def require(request: Request, key: str):
    checker = KeyChecker(api_key=key)
    helper_check(key)
    return await checker(request)
'''

USER_DEFINES = '''\
from fastapi import Request


class KeyChecker:
    def __init__(self, api_key):
        self.api_key = api_key


def helper_check(key):
    return bool(key)


async def require(request: Request, key: str):
    checker = KeyChecker(api_key=key)
    helper_check(key)
    return await checker(request)
'''

META = SimpleNamespace(entry_point="require", exports=[], requires=[],
                       guards=[Guard(kind="must_call", names=["lnbits.decorators.KeyChecker",
                                                               "lnbits.decorators.helper_check"])])


@pytest.mark.parametrize("module", ["lnbits.decorators", None])
def test_pattern_imports_what_the_user_file_defines(module):
    pu = codeunit.build_unit_from_source(PATTERN_IMPORTS, "require")
    uu = codeunit.build_unit_from_source(USER_DEFINES, "require", module)
    a = deviation.analyze(pu, uu, pattern_key="auth.x@v1", pattern_function="require", meta=META)
    assert a.deviations == [] and a.shape_match and a.resolution == "full"


def test_pattern_defines_what_the_user_file_imports():
    meta = SimpleNamespace(**{**META.__dict__, "guards": [Guard(kind="must_call", names=["KeyChecker"])]})
    pu = codeunit.build_unit_from_source(USER_DEFINES, "require")
    uu = codeunit.build_unit_from_source(PATTERN_IMPORTS, "require", "lnbits.views")
    a = deviation.analyze(pu, uu, pattern_key="auth.x@v1", pattern_function="require", meta=meta)
    assert a.deviations == [] and a.shape_match


def test_same_names_on_both_sides_give_the_same_keys():
    for module in (None, "lnbits.decorators"):
        pu = codeunit.build_unit_from_source(USER_DEFINES, "require")
        uu = codeunit.build_unit_from_source(USER_DEFINES, "require", module)
        pu, uu, assumed = deviation.bind(pu, uu)
        assert [c.key for c in codeunit.calls(pu)] == [c.key for c in codeunit.calls(uu)]
        assert assumed == {}


def test_a_genuinely_different_class_is_still_reported():
    pu = codeunit.build_unit_from_source(PATTERN_IMPORTS, "require")
    uu = codeunit.build_unit_from_source(USER_DEFINES, "require", "otherapp.auth")
    a = deviation.analyze(pu, uu, pattern_key="auth.x@v1", pattern_function="require", meta=META)
    assert {d.code for d in a.deviations} >= {"PC100"}
    assert any(re.search(r"no longer calls `lnbits.decorators.KeyChecker`", d.message) for d in a.deviations)
