"""Provenance: markers, approvals in comment blocks, and inferred derivation (v4 Part A)."""

from __future__ import annotations

import ast

import pytest

from conftest import REPO_ROOT, edit_yaml, pattern_dir
from pcat import provenance
from pcat.serving import CatalogService

SOURCE = '''\
import os

# pcat: auth.password.pbkdf2@v1
def make_hash(password):
    return password


# some note
# pcat-allow: PC101 -- the upstream API only treats timeouts as transient
# pcat: http.get_with_retry.requests
@decorator
def fetch(url):
    return url


def plain(x):
    return x


class Thing:
    # pcat: text.slugify.ascii@v2
    def method(self, text):
        return text
'''


def infos():
    return {i.qualname: i for i in provenance.functions(SOURCE)}


def test_marker_with_version():
    m = infos()["make_hash"].marker
    assert (m.pattern_id, m.version, m.line, m.ref) == ("auth.password.pbkdf2", 1, 3, "auth.password.pbkdf2@v1")


def test_marker_without_version_above_decorator_and_approvals():
    info = infos()["fetch"]
    assert info.marker.pattern_id == "http.get_with_retry.requests" and info.marker.version is None
    assert info.marker.ref == "http.get_with_retry.requests"
    assert [(a.code, a.reason, a.problem) for a in info.approvals] == [
        ("PC101", "the upstream API only treats timeouts as transient", None)]


def test_multiple_markers_in_a_file_and_methods():
    found = {q: i.marker.ref for q, i in infos().items() if i.marker}
    assert found == {"make_hash": "auth.password.pbkdf2@v1", "fetch": "http.get_with_retry.requests",
                     "Thing.method": "text.slugify.ascii@v2"}
    assert infos()["plain"].marker is None


def test_marker_must_be_directly_above():
    src = "# pcat: auth.password.pbkdf2@v1\n\ndef f():\n    pass\n"
    assert provenance.functions(src)[0].marker is None


@pytest.mark.parametrize("line,problem", [
    ("# pcat: Not An Id", "malformed pcat marker"),
    ("# pcat:", "malformed pcat marker"),
])
def test_malformed_markers_are_reported(line, problem):
    info = provenance.functions(f"{line}\ndef f():\n    pass\n")[0]
    assert info.marker is None and problem in info.problems[0][1]


def test_two_markers_on_one_function():
    src = "# pcat: a.b@v1\n# pcat: c.d@v2\ndef f():\n    pass\n"
    info = provenance.functions(src)[0]
    assert info.marker.ref == "a.b@v1" and "more than one" in info.problems[0][1]


@pytest.mark.parametrize("rest,code,problem", [
    ("PC101 -- connection errors must fail fast here", "PC101", None),
    ("PC101", "PC101", "no reason"),
    ("PC101 --   ", "PC101", "no reason"),
    ("PC101 -- too short", "PC101", "shorter than 10"),
    ("PC101, PC102 -- two codes on one line", None, "malformed"),
    ("whatever", None, "malformed"),
])
def test_approval_parsing(rest, code, problem):
    a = provenance.parse_approval(rest, 7)
    assert a.code == code and a.line == 7
    assert (a.problem is None) if problem is None else (problem in a.problem)


def test_get_pattern_output_carries_markers():
    service = CatalogService(REPO_ROOT)
    code = service.get_pattern("auth.password.pbkdf2", {"f0": "make_hash"})["code"]
    infos_ = {i.qualname: i for i in provenance.functions(code)}
    assert {q for q, i in infos_.items() if i.marker} == {"make_hash", "verify_password", "needs_rehash"}
    assert all(i.marker.ref == "auth.password.pbkdf2@v1" for i in infos_.values() if i.marker)
    assert "Keep the '# pcat: <id>@v<N>' comment" in service.instructions()


@pytest.fixture(scope="module")
def refs():
    return provenance.references(REPO_ROOT)


def test_references_cover_entry_points_and_exports(refs):
    keys = {(r.pattern_id, r.function) for r in refs}
    assert ("auth.password.pbkdf2", "verify_password") in keys
    assert ("config.env.load_settings", "parse_bool") in keys


def test_references_exclude_deprecated(root):
    edit_yaml(pattern_dir(root, "search.binary_search.recursive"), status="deprecated",
              replaced_by="search.binary_search.iterative")
    ids = {r.pattern_id for r in provenance.references(root)}
    assert "search.binary_search.recursive" not in ids and "search.binary_search.iterative" in ids
    assert "search.binary_search.recursive" in {
        r.pattern_id for r in provenance.references(root, include_deprecated=True)}


def test_inference_applies_the_threshold(refs):
    service = CatalogService(REPO_ROOT)
    code = service.get_pattern("http.get_with_retry.requests", {"f0": "fetch"})["code"]
    tree = ast.parse(code)
    func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "fetch")
    inf = provenance.infer(func, refs)
    assert (inf.pattern_id, inf.function, inf.similarity, inf.derived) == (
        "http.get_with_retry.requests", "get_with_retry", 1.0, True)
    assert provenance.infer(func, refs, threshold=1.01).derived is False
    unrelated = ast.parse("def f(a, b):\n    return sorted(set(a) ^ set(b), key=str)\n").body[0]
    assert provenance.infer(unrelated, refs).derived is False


def test_calibrated_threshold_matches_the_constant():
    import json

    data = json.loads((REPO_ROOT / "experiments/linter/inference_calibration.json").read_text())
    assert data["chosen_threshold"] == provenance.INFERENCE_THRESHOLD
