"""Deviation analysis (v4 Part C): every code on a minimal fixture, none from renaming alone."""

from __future__ import annotations

import ast
from types import SimpleNamespace

import pytest

from conftest import REPO_ROOT
from pcat import catalog as cat
from pcat import codeunit, deviation
from pcat.schema import Guard
from pcat.serving import CatalogService

PATTERN = '''\
"""Pattern docstring."""
import requests

LIMIT = 100


def helper(text):
    return text.strip()


def f(url, attempts=3, timeout=10.0):
    """Fetch."""
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    for i in range(attempts):
        try:
            response = requests.get(url, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout):
            if i == attempts - 1:
                raise
            continue
        response.raise_for_status()
        return helper(response.text)[:LIMIT]
'''

# The same code with every name changed, comments and a docstring added, aliases for imports.
RENAMED = '''\
import requests as rq

MAX_CHARS = 100  # renamed constant


def clean(value):
    # helper, renamed
    return value.strip()


def fetch(address, tries=3, wait=10.0):
    """User docstring."""
    if tries < 1:
        raise ValueError("attempts must be >= 1")
    for n in range(tries):
        try:
            resp = rq.get(address, timeout=wait)
        except (rq.ConnectionError, rq.Timeout):
            if n == tries - 1:
                raise
            continue
        resp.raise_for_status()
        return clean(resp.text)[:MAX_CHARS]
'''

META = SimpleNamespace(entry_point="f", exports=[], requires=["requests>=2.31,<3"], guards=[])


def run(user: str, meta=META, name: str = "fetch") -> deviation.Analysis:
    pu = codeunit.build_unit_from_source(PATTERN, "f")
    uu = codeunit.build_unit_from_source(user, name)
    return deviation.analyze(pu, uu, pattern_key="demo.fetch@v1", pattern_function="f", meta=meta)


def codes(user: str, **kw) -> list[str]:
    return [d.code for d in run(user, **kw).deviations]


def mutate(old: str, new: str, count: int = 1) -> str:
    assert RENAMED.count(old) >= 1, old
    return RENAMED.replace(old, new, count)


def test_renaming_alone_reports_nothing():
    analysis = run(RENAMED)
    assert analysis.deviations == [] and analysis.shape_match
    assert codes(PATTERN, name="f") == []


def test_pc101_exception_narrowed_uses_user_names():
    a = run(mutate("except (rq.ConnectionError, rq.Timeout):", "except rq.Timeout:"))
    assert [d.code for d in a.deviations] == ["PC101"]  # the changed handler is explained by PC101
    d = a.deviations[0]
    assert d.severity == "high" and d.line == 18
    assert d.message.startswith("`fetch` no longer catches `rq.ConnectionError` (it catches requests.Timeout)")
    assert d.message.endswith("the pattern does: `except (rq.ConnectionError, rq.Timeout)`")


def test_pc102_validation_removed_message_in_user_names():
    user = mutate('    if tries < 1:\n        raise ValueError("attempts must be >= 1")\n', "")
    a = run(user)
    assert "PC102" in [d.code for d in a.deviations]
    msg = next(d.message for d in a.deviations if d.code == "PC102")
    assert "`if tries < 1: raise ValueError(...)`" in msg and "attempts <" not in msg


def test_pc102_reraise_removed():
    user = mutate("            if n == tries - 1:\n                raise\n", "")
    assert "PC102" in codes(user)


def test_pc103_library_swapped():
    user = RENAMED.replace("import requests as rq", "import httpx as rq")
    a = run(user)
    d = next(d for d in a.deviations if d.code == "PC103")
    assert "no longer uses `requests`" in d.message and "`httpx` instead" in d.message
    stdlib_only = SimpleNamespace(**{**META.__dict__, "requires": []})
    assert "PC103" in codes(user, meta=stdlib_only)  # requests dropped, httpx added: a swap


def test_adding_a_third_party_import_alone_is_not_a_swap():
    # v4.1: a stdlib-only change is PC103 low; a new third-party library alone is medium
    user = "import json\n" + mutate("        resp.raise_for_status()\n",
                                    "        resp.raise_for_status()\n        json.dumps(1)\n")
    assert [(d.code, d.severity) for d in run(user).deviations if d.code == "PC103"] == [("PC103", "low")]
    third = "import orjson\n" + mutate("        resp.raise_for_status()\n",
                                       "        resp.raise_for_status()\n        orjson.dumps(1)\n")
    assert [(d.code, d.severity) for d in run(third).deviations if d.code == "PC103"] == [("PC103", "medium")]


def test_pc104_broad_except_added():
    user = mutate("            continue\n", "            continue\n        except Exception:\n            return None\n")
    a = run(user)
    d = next(d for d in a.deviations if d.code == "PC104")
    assert d.severity == "medium" and "`except Exception`" in d.message


def test_pc105_call_removed_and_pc100_when_guarded():
    user = mutate("        resp.raise_for_status()\n", "")
    assert "PC105" in codes(user)
    guarded = SimpleNamespace(**{**META.__dict__, "guards": [Guard(kind="must_call", names=[".raise_for_status"])]})
    got = codes(user, meta=guarded)
    assert "PC100" in got and "PC105" not in got  # the guard explains it


def test_pc106_private_access_added():
    user = mutate("        return clean(resp.text)", "        return clean(resp._content.decode())")
    d = next(d for d in run(user).deviations if d.code == "PC106")
    assert "private `_content`" in d.message and d.line == 23


def test_pc107_signature_changes():
    assert "PC107" in codes(mutate("wait=10.0)", "wait=10.0, verify=True)"))
    assert "PC107" in codes(mutate("tries=3, ", ""))
    msg = [d.message for d in run(mutate("wait=10.0)", "wait=None)")).deviations if d.code == "PC107"]
    assert msg == ["parameter `wait` of `fetch`: default changed from `10.0` to `None`"]


def test_pc108_call_added():
    a = run(mutate("    if tries < 1:", "    print(address)\n    if tries < 1:"))
    d = next(d for d in a.deviations if d.code == "PC108")
    assert d.severity == "low" and "`print`" in d.message and d.line == 13


def test_pc109_literal_changes_only():
    a = run(mutate("MAX_CHARS = 100", "MAX_CHARS = 200").replace("wait=10.0", "wait=5.0"))
    assert {d.code for d in a.deviations} == {"PC109"} and a.shape_match
    messages = sorted(d.message for d in a.deviations)
    assert messages == ["`MAX_CHARS` (pattern: `LIMIT`) changed from 100 to 200",
                        "default of `wait` changed from `10.0` to `5.0`"]
    inline = run(mutate('"attempts must be >= 1"', '"tries must be positive"'))
    assert [d.code for d in inline.deviations] == ["PC109"]


def test_pc110_structure_change():
    a = run(mutate("    for n in range(tries):", "    count = 0\n    for n in range(tries):"))
    assert [d.code for d in a.deviations] == ["PC110"] and not a.shape_match


def test_helper_defined_elsewhere_is_not_removed():
    user = RENAMED.replace("def clean(value):\n    # helper, renamed\n    return value.strip()\n", "")
    user = user.replace("clean(", "helper(")
    assert codes(user) == []


def test_guarded_value_reported_as_pc100_not_pc109():
    guarded = SimpleNamespace(**{**META.__dict__, "guards": [Guard(kind="max_value", target="LIMIT", value=100)]})
    a = run(mutate("MAX_CHARS = 100", "MAX_CHARS = 5000"), meta=guarded)
    assert [d.code for d in a.deviations] == ["PC100"]
    assert a.deviations[0].message.startswith("`MAX_CHARS` (pattern: `LIMIT`) is 5000, above the reviewed maximum 100")
    ok = run(mutate("MAX_CHARS = 100", "MAX_CHARS = 50"), meta=guarded)
    assert ok.deviations == []  # within the guard: not a literal change to report


def test_diff_is_rendered_in_user_names():
    a = run(mutate("except (rq.ConnectionError, rq.Timeout):", "except rq.Timeout:"))
    lines = a.diff.splitlines()
    assert lines[:2] == ["--- demo.fetch@v1 (in your names)", "+++ your fetch"]
    changed = [x for x in lines[2:] if x[:1] in "+-" ]
    assert changed == ["-        except (rq.ConnectionError, rq.Timeout):", "+        except rq.Timeout:"]


def test_output_is_deterministic():
    user = mutate("except (rq.ConnectionError, rq.Timeout):", "except Exception:")
    assert run(user).to_dict() == run(user).to_dict()


# Real catalog patterns ------------------------------------------------------


@pytest.fixture(scope="module")
def service():
    return CatalogService(REPO_ROOT)


def analyze_code(code: str, pattern_id: str, function: str):
    tree = ast.parse(code)
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == function)
    return deviation.analyze_function(tree, node, cat.get_one(REPO_ROOT, pattern_id))


@pytest.mark.parametrize("pattern_id", [
    "auth.jwt.create_access_token", "auth.password.pbkdf2", "db.pagination.select_page",
    "http.get_with_retry.requests", "config.env.load_settings", "ratelimit.token_bucket.check",
    "importers.users_csv.parse", "text.slugify.ascii",
])
def test_get_pattern_output_has_no_deviations(service, pattern_id):
    got = service.get_pattern(pattern_id)
    pattern = cat.get_one(REPO_ROOT, pattern_id)
    for function in [got["entry_point"], *pattern.meta.exports]:
        a = analyze_code(got["code"], pattern_id, function)
        assert a.deviations == [] and a.shape_match, (function, a.deviations)


def test_pbkdf2_lowered_iterations_is_a_guard_violation(service):
    code = service.get_pattern("auth.password.pbkdf2", {"f0": "make_hash", "c1": "FLOOR"})["code"]
    code = code.replace("FLOOR = 600000", "FLOOR = 1000")
    a = analyze_code(code, "auth.password.pbkdf2", "make_hash")
    assert [(d.code, d.severity) for d in a.deviations] == [("PC100", "high")]
    assert a.deviations[0].message.startswith("`FLOOR` (pattern: `MIN_ITERATIONS`) is 1000, below")


def test_verify_without_compare_digest(service):
    code = service.get_pattern("auth.password.pbkdf2")["code"]
    code = code.replace("return hmac.compare_digest(key, expected)", "return key == expected")
    a = analyze_code(code, "auth.password.pbkdf2", "verify_password")
    assert ("PC100", "high") in [(d.code, d.severity) for d in a.deviations]
    assert any("hmac.compare_digest" in d.message for d in a.deviations)


def test_choose_pattern_function_by_name_then_similarity(service):
    code = service.get_pattern("auth.password.pbkdf2", {"f0": "make_hash"})["code"]
    tree = ast.parse(code)
    nodes = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    pattern = cat.get_one(REPO_ROOT, "auth.password.pbkdf2")
    assert deviation.choose_pattern_function(nodes["verify_password"], pattern) == "verify_password"
    assert deviation.choose_pattern_function(nodes["make_hash"], pattern) == "hash_password"


# v4.1: PC103 severity levels, PC110 suppression, must_include -------------------


def test_pc103_severity_levels():
    requires = META
    swapped = RENAMED.replace("import requests as rq", "import httpx as rq")
    assert [(d.code, d.severity) for d in run(swapped, meta=requires).deviations if d.code == "PC103"] == [
        ("PC103", "high")]  # a required library dropped or replaced
    no_requires = SimpleNamespace(**{**META.__dict__, "requires": []})
    assert [(d.code, d.severity) for d in run(swapped, meta=no_requires).deviations if d.code == "PC103"] == [
        ("PC103", "medium")]  # a new third-party library, nothing required dropped
    std = "import io\n" + mutate("        return clean(resp.text)", "        return clean(io.StringIO(resp.text).read())")
    assert [(d.code, d.severity) for d in run(std).deviations if d.code == "PC103"] == [("PC103", "low")]


def test_pc110_does_not_repeat_a_line_with_another_deviation():
    # one changed statement carrying a new call: PC108 on that line, no PC110 for it
    user = mutate("        resp.raise_for_status()\n", "        resp.raise_for_status() or print(resp)\n")
    got = [(d.code, d.line) for d in run(user).deviations]
    assert ("PC108", 22) in got and not [c for c, _ in got if c == "PC110"]
    # a must_not_call line (the v4 POST case) is not repeated as PC110 either
    post = RENAMED.replace("rq.get(address", "rq.post(address")
    guarded = SimpleNamespace(**{**META.__dict__, "guards": [Guard(kind="must_not_call", names=["requests.post"])]})
    got = [(d.code, d.line) for d in run(post, meta=guarded).deviations]
    assert ("PC100", 17) in got and "PC110" not in [c for c, _ in got]
    # a genuinely new statement still is PC110
    assert "PC110" in codes(mutate("    for n in range(tries):", "    count = 0\n    for n in range(tries):"))


def test_must_include_replaces_pc109_for_its_target():
    guarded = SimpleNamespace(**{**META.__dict__, "guards": [
        Guard(kind="must_include", target="RETRY", values=[429])]})
    pattern = PATTERN.replace("LIMIT = 100\n", "LIMIT = 100\nRETRY = (429, 500)\n").replace(
        "        response.raise_for_status()\n", "        if response.status_code in RETRY:\n            continue\n        response.raise_for_status()\n")
    user = RENAMED.replace("MAX_CHARS = 100  # renamed constant\n", "MAX_CHARS = 100\nRETRY = (500,)\n").replace(
        "        resp.raise_for_status()\n", "        if resp.status_code in RETRY:\n            continue\n        resp.raise_for_status()\n")
    pu = codeunit.build_unit_from_source(pattern, "f")
    uu = codeunit.build_unit_from_source(user, "fetch")
    a = deviation.analyze(pu, uu, pattern_key="demo.fetch@v1", pattern_function="f", meta=guarded)
    assert [(d.code, d.severity) for d in a.deviations] == [("PC100", "high")]
    assert a.deviations[0].message.startswith("`RETRY` no longer includes 429")
