"""Guards (v4 Part B): schema, each kind on compliant/violating code, validation check 11."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from conftest import edit_yaml, pattern_dir
from pcat import catalog as cat
from pcat import codeunit, guards
from pcat.schema import Guard


def run(source: str, name: str, **guard) -> list[guards.GuardResult]:
    unit = codeunit.build_unit_from_source(source, name)
    return guards.check(unit, [(0, Guard(**guard))])


def ok(source: str, name: str = "f", **guard) -> bool:
    return all(r.ok for r in run(source, name, **guard))


CATCH_OK = """
import requests
from requests import Timeout as T

def f(url):
    try:
        return requests.get(url)
    except (requests.exceptions.ConnectionError, T):
        return None
"""
CATCH_NARROW = """
import requests

def fetch_it(url):
    try:
        return requests.get(url)
    except requests.Timeout:
        return None
"""


def test_must_catch():
    g = dict(kind="must_catch", names=["requests.ConnectionError", "requests.Timeout"])
    assert ok(CATCH_OK, **g)
    results = run(CATCH_NARROW, "fetch_it", **g)
    bad = guards.violations(results)
    assert [r.item for r in bad] == ["requests.ConnectionError"]
    assert "`fetch_it` no longer handles `requests.ConnectionError`" in bad[0].message
    assert "it catches requests.Timeout" in bad[0].message and bad[0].line == 7


def test_must_catch_accepts_broad_handlers_and_builtin_superclasses():
    broad = "def f():\n    try:\n        pass\n    except Exception:\n        pass\n"
    sup = "def f():\n    try:\n        pass\n    except OSError:\n        pass\n"
    assert ok(broad, kind="must_catch", names=["requests.Timeout"])
    assert ok(sup, kind="must_catch", names=["ConnectionError", "TimeoutError"])
    assert not ok(sup, kind="must_catch", names=["ValueError"])


def test_must_catch_in_a_helper_counts():
    src = ("def helper(x):\n    try:\n        return int(x)\n    except ValueError:\n        return 0\n\n"
           "def f(x):\n    return helper(x)\n")
    assert ok(src, kind="must_catch", names=["ValueError"])


def test_must_call():
    good = "from hmac import compare_digest as cd\n\ndef f(a, b):\n    return cd(a, b)\n"
    bad = "def f(a, b):\n    return a == b\n"
    method = "def f(r):\n    r.raise_for_status()\n    return r\n"
    assert ok(good, kind="must_call", names=["hmac.compare_digest"])
    assert not ok(bad, kind="must_call", names=["hmac.compare_digest"])
    assert ok(method, kind="must_call", names=[".raise_for_status"])
    assert not ok(bad, kind="must_call", names=[".raise_for_status"])


def test_must_not_call():
    src = "import hashlib\n\ndef f(p):\n    return hashlib.md5(p).hexdigest()\n"
    results = run(src, "f", kind="must_not_call", names=["hashlib.md5", "eval"])
    assert [(r.item, r.ok) for r in results] == [("hashlib.md5", False), ("eval", True)]
    assert results[0].line == 4 and "`f` calls `hashlib.md5`" in results[0].message
    assert ok("def f(s):\n    return s.post\n", kind="must_not_call", names=[".post"])  # not a call
    assert not ok("def f(s):\n    return s.post('u')\n", kind="must_not_call", names=[".post"])


def test_min_and_max_value_on_constants_and_defaults():
    src = "LOW = 1000\nHIGH = 50\n\ndef f(x, iterations=LOW, cap=HIGH, other=7):\n    return x\n"
    assert not ok(src, kind="min_value", target="LOW", value=600000)
    assert not ok(src, kind="min_value", target="iterations", value=600000)
    assert ok(src, kind="max_value", target="cap", value=100)
    assert not ok(src, kind="max_value", target="other", value=5)
    msg = run(src, "f", kind="min_value", target="iterations", value=600000)[0].message
    assert msg.startswith("`iterations` is 1000, below the reviewed minimum 600000")


def test_value_guard_uses_the_users_names_and_reports_missing_targets():
    src = "PBKDF2_MIN = 100\n\ndef f(x):\n    return x > PBKDF2_MIN\n"
    unit = codeunit.build_unit_from_source(src, "f")
    g = [(0, Guard(kind="min_value", target="MIN_ITERATIONS", value=600000))]
    res = guards.check(unit, g, {"MIN_ITERATIONS": "PBKDF2_MIN"})[0]
    assert not res.ok and res.message.startswith("`PBKDF2_MIN` (pattern: `MIN_ITERATIONS`) is 100")
    missing = guards.check(unit, g)[0]
    assert missing.ok and not missing.found


def test_must_not_import():
    src = "import re\nfrom re import compile as c\n\ndef f(s):\n    return re.match('x', s) and c\n"
    assert not ok(src, kind="must_not_import", names=["re"])
    assert ok("import requests\n\ndef f():\n    return requests\n", kind="must_not_import", names=["re"])
    inner = "def f(s):\n    import pickle\n    return pickle.loads(s)\n"
    assert not ok(inner, kind="must_not_import", names=["pickle"])


def test_must_raise():
    good = "def f(x):\n    if x < 1:\n        raise ValueError('x')\n    return x\n"
    bad = "def f(x):\n    return max(x, 1)\n"
    assert ok(good, kind="must_raise", names=["ValueError"])
    assert not ok(bad, kind="must_raise", names=["ValueError"])
    assert not ok(good, kind="must_raise", names=["TypeError"])


def test_raise_target_is_not_a_call():
    unit = codeunit.build_unit_from_source("def f(x):\n    raise ValueError(str(x))\n", "f")
    assert [c.key for c in codeunit.calls(unit)] == ["str"]


@pytest.mark.parametrize("guard,error", [
    (dict(kind="must_call"), "needs names"),
    (dict(kind="must_call", names=["a b"]), "dotted name"),
    (dict(kind="must_call", names=["x", "x"]), "unique"),
    (dict(kind="min_value", target="X"), "needs target"),
    (dict(kind="min_value", names=["X"], target="X", value=1), "not names"),
    (dict(kind="must_raise", names=["ValueError"], value=1), "not target"),
    (dict(kind="must_not_import", names=[".re"]), "cannot start"),
    (dict(kind="nope", names=["x"]), "kind"),
])
def test_invalid_guards_rejected(guard, error):
    with pytest.raises(ValidationError, match=error):
        Guard(**guard)


def test_guard_function_must_be_public(root):
    folder = pattern_dir(root, "text.slugify.ascii")
    edit_yaml(folder, guards=[{"kind": "must_call", "names": ["re.sub"], "function": "helper"}])
    problems = cat.validate(root, run_tests=False)  # invalid metadata cannot be selected by id
    assert any(p.check == "1" and "entry_point or an export" in p.message for p in problems)


def test_check_11_guard_must_hold_on_its_own_pattern(root):
    folder = pattern_dir(root, "text.slugify.ascii")
    edit_yaml(folder, guards=[{"kind": "must_call", "names": ["hashlib.sha256"]},
                              {"kind": "min_value", "target": "NOT_THERE", "value": 3}])
    problems = [p for p in cat.validate(root, ["text.slugify.ascii"], run_tests=False) if p.check == "11"]
    assert len(problems) == 2
    assert "guard 1 (must_call) does not hold on the pattern itself" in problems[0].message
    assert "target 'NOT_THERE' not found" in problems[1].message


def test_guards_do_not_change_fingerprints_or_the_index(root):
    before = {p.label: p.meta.fingerprint for p in cat.load_catalog(root)}
    folder = pattern_dir(root, "text.slugify.ascii")
    edit_yaml(folder, guards=[{"kind": "must_not_call", "names": ["eval"], "reason": "never evaluate"}])
    assert not [p for p in cat.validate(root, ["text.slugify.ascii"], run_tests=False)]
    after = {p.label: cat.analyze_pattern(p).fingerprint for p in cat.load_catalog(root)}
    assert before == after


def test_real_catalog_guards_hold():
    from conftest import REPO_ROOT

    with_guards = [p for p in cat.load_catalog(REPO_ROOT) if p.meta and p.meta.guards]
    assert {p.meta.id.split(".")[0] for p in with_guards} == {
        "auth", "config", "db", "http", "importers", "ratelimit"}
    assert len(with_guards) == 7
    problems = [p for p in cat.validate(REPO_ROOT, run_tests=False) if p.check == "11"]
    assert problems == []


# v4.1: must_include ----------------------------------------------------------


def test_must_include_passes_and_fails():
    src = "STATUSES = (429, 500, 502)\n\ndef f(x, codes=(1, 2), names=STATUSES):\n    return x in STATUSES\n"
    assert ok(src, kind="must_include", target="STATUSES", values=[429, 500])
    res = run(src.replace("(429, 500, 502)", "(500, 502)"), "f", kind="must_include",
              target="STATUSES", values=[429, 500])
    assert not res[0].ok and res[0].message.startswith("`STATUSES` no longer includes 429; the reviewed pattern requires 429, 500")
    assert ok(src, kind="must_include", target="codes", values=[1])  # a default argument
    assert ok(src, kind="must_include", target="names", values=[502])  # default naming a constant
    assert not ok(src.replace("(429, 500, 502)", "429"), kind="must_include", target="STATUSES", values=[429])
    missing = run(src, "f", kind="must_include", target="NOPE", values=[1])[0]
    assert missing.ok and not missing.found


@pytest.mark.parametrize("guard,error", [
    (dict(kind="must_include", target="X"), "needs target"),
    (dict(kind="must_include", target="X", values=[1], value=2), "not names/value"),
    (dict(kind="must_include", target="X", values=[1, 1]), "unique"),
    (dict(kind="min_value", target="X", value=1, values=[1]), "not names"),
])
def test_invalid_must_include(guard, error):
    with pytest.raises(ValidationError, match=error):
        Guard(**guard)


def test_check_11_covers_must_include(root):
    folder = pattern_dir(root, "http.get_with_retry.requests")
    import yaml

    data = yaml.safe_load((folder / "pattern.yaml").read_text())
    data["guards"] = [g for g in data["guards"] if g["kind"] != "must_include"] + [
        {"kind": "must_include", "target": "RETRY_STATUSES", "values": [408, 429]}]
    edit_yaml(folder, guards=data["guards"])
    problems = [p for p in cat.validate(root, ["http.get_with_retry.requests"], run_tests=False) if p.check == "11"]
    assert len(problems) == 1 and "(must_include) does not hold" in problems[0].message
    assert "no longer includes 408" in problems[0].message


def test_http_pattern_has_the_429_guard():
    from conftest import REPO_ROOT

    meta = cat.get_one(REPO_ROOT, "http.get_with_retry.requests").meta
    [g] = [g for g in meta.guards if g.kind == "must_include"]
    assert (g.target, g.values) == ("RETRY_STATUSES", [429, 500, 502, 503, 504])
