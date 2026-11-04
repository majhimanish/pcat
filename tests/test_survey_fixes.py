"""v5.1 Part E: regression tests for false-positive causes found by the survey on real code."""

from __future__ import annotations

from conftest import REPO_ROOT
from pcat import codeunit, deviation, lint

CTFD = REPO_ROOT / "experiments" / "v5" / "catalogs" / "ctfd"

PATTERN = "def lookup(user_id, default=None):\n    return fetch(user_id) or default\n"
METHOD = ("class Resource:\n    def get(self, award_id, default=None):\n"
          "        return fetch(award_id) or default\n")


def test_method_receiver_is_not_a_parameter():
    """Survey: CTFd API methods `get(self, award_id)` reported `adds parameter award_id`
    because `self` was aligned with the pattern's first parameter."""
    import ast

    tree = ast.parse(METHOD)
    node = tree.body[0].body[0]
    a = deviation.analyze(codeunit.build_unit_from_source(PATTERN, "lookup"), codeunit.build_unit(tree, node),
                          pattern_key="x.y@v1", pattern_function="lookup")
    assert [d for d in a.deviations if d.code == "PC107"] == []
    extra = METHOD.replace("default=None):", "default=None, other=1):")
    tree = ast.parse(extra)
    a = deviation.analyze(codeunit.build_unit_from_source(PATTERN, "lookup"),
                          codeunit.build_unit(tree, tree.body[0].body[0]),
                          pattern_key="x.y@v1", pattern_function="lookup")
    assert [d.message for d in a.deviations if d.code == "PC107"] == ["`get` adds parameter `other`"]


def test_a_method_pattern_keeps_comparing_its_receiver():
    pattern = "def get(self, key):\n    return self.cache[key]\n"
    user = "def get(cls, key):\n    return cls.cache[key]\n"
    a = deviation.analyze(codeunit.build_unit_from_source(pattern, "get"), codeunit.build_unit_from_source(user, "get"),
                          pattern_key="x.y@v1", pattern_function="get")
    assert [d.code for d in a.deviations if d.code == "PC107"] == []  # renamed receiver, same position


def test_nested_wrapper_is_not_reported_twice(tmp_path):
    """Survey: CTFd's `registered_only` and its inner `_registered_only` were both inferred
    from decorators.authed_only; the inner function is part of the outer one's analysis."""
    impl = next(CTFD.rglob("authed_only/impl.py")).read_text()
    code = impl.replace("authed_only", "members_only")
    path = tmp_path / "views.py"
    path.write_text(code)
    report = lint.lint_paths([str(path)], CTFD, include_inferred=True)
    names = [f.function for f in report.findings]
    assert names == ["members_only"], names


PATTERN_CONN = '''\
from lnbits.core.db import db


async def delete_row(*, ext_id, conn=None):
    await (conn or db).execute("DELETE FROM t WHERE id = :id", {"id": ext_id})
'''


def test_call_through_conn_or_db_matches_a_call_on_db():
    """Survey: LNbits CRUD helpers calling `db.execute(...)` were reported as no longer
    calling the pattern's `(conn or db).execute` (PC105) and adding `db.execute` (PC108)."""
    user = PATTERN_CONN.replace("(conn or db).execute", "db.execute").replace("*, ext_id, conn=None", "*, ext_id")
    a = deviation.analyze(codeunit.build_unit_from_source(PATTERN_CONN, "delete_row"),
                          codeunit.build_unit_from_source(user, "delete_row"),
                          pattern_key="x.y@v1", pattern_function="delete_row")
    assert [d.code for d in a.deviations if d.code in ("PC105", "PC108")] == []
    swapped = user.replace("db.execute", "db.fetchone")
    a = deviation.analyze(codeunit.build_unit_from_source(PATTERN_CONN, "delete_row"),
                          codeunit.build_unit_from_source(swapped, "delete_row"),
                          pattern_key="x.y@v1", pattern_function="delete_row")
    assert {d.code for d in a.deviations} >= {"PC105", "PC108"}  # a different call is still reported


def test_method_guard_targets_match_calls_on_imported_objects():
    from pcat import guards
    from pcat.schema import Guard

    unit = codeunit.build_unit_from_source(
        "from lnbits.core.db import db\n\n\nasync def f(name):\n    return await db.fetchone(name.lower())\n", "f")
    res = guards.check(unit, [(0, Guard(kind="must_call", names=[".fetchone", ".lower"]))])
    assert all(r.ok for r in res)
    unit = codeunit.build_unit_from_source("import requests\n\n\ndef f(u):\n    return requests.post(u)\n", "f")
    [r] = guards.check(unit, [(0, Guard(kind="must_not_call", names=[".post"]))])
    assert not r.ok
