"""v4.1 approvals: hash binding (Part A), states against a base ref (Part B)."""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from conftest import REPO_ROOT
from pcat import provenance
from pcat.cli import app
from pcat.serving import CatalogService

HTTP = "http.get_with_retry.requests"
NARROW = ("except (requests.ConnectionError, requests.Timeout):", "except requests.Timeout:")
REASON = "this API only treats timeouts as transient; connection errors must fail fast"


@pytest.fixture(scope="module")
def narrowed() -> str:
    return CatalogService(REPO_ROOT).get_pattern(HTTP, {"f0": "fetch"})["code"].replace(*NARROW)


def hash_of(code: str, name: str = "fetch") -> str:
    node = next(n for n in ast.walk(ast.parse(code)) if isinstance(n, ast.FunctionDef) and n.name == name)
    return provenance.function_hash(node)


def with_approval(code: str, line: str) -> str:
    return code.replace(f"# pcat: {HTTP}@v1\ndef fetch(", f"{line}\n# pcat: {HTTP}@v1\ndef fetch(")


def lint(*args: str):
    return CliRunner().invoke(app, ["lint", *args, "--catalog", str(REPO_ROOT)])


def lint_json(*args: str) -> dict:
    return json.loads(lint(*args, "--format", "json").output)


# Part A: parsing and hashes ------------------------------------------------


@pytest.mark.parametrize("rest,code,hash_,reason,problem", [
    ("PC100 #a1b2c3d4 -- the request needs this change", "PC100", "a1b2c3d4", "the request needs this change", None),
    ("PC100 #A1B2C3D4 -- upper-case hashes are accepted", "PC100", "a1b2c3d4", "upper-case hashes are accepted", None),
    ("PC100 -- v4 format without a hash still parses", "PC100", None, "v4 format without a hash still parses", None),
    ("PC100 #a1b2 -- too short a hash is malformed", None, None, "", "malformed"),
    ("PC100 #a1b2c3d4", "PC100", "a1b2c3d4", "", "no reason"),
])
def test_approval_parsing_with_and_without_hash(rest, code, hash_, reason, problem):
    a = provenance.parse_approval(rest, 3)
    assert (a.code, a.hash, a.reason) == (code, hash_, reason)
    assert (a.problem is None) if problem is None else (problem in a.problem)


def test_function_hash_ignores_comments_names_and_docstrings(narrowed):
    h = hash_of(narrowed)
    assert len(h) == 8 and int(h, 16) >= 0
    commented = with_approval(narrowed, f"# pcat-allow: PC100 #{h} -- {REASON}").replace(
        "    if attempts < 1:", '    """doc."""\n    # comment\n    if attempts < 1:')
    assert hash_of(commented) == h
    assert hash_of(narrowed.replace("def fetch(", "def get_it(").replace("fetch", "get_it"), "get_it") == h
    assert hash_of(narrowed.replace("attempts < 1", "attempts < 2")) != h


def test_matching_hash_approves(tmp_path, narrowed):
    path = tmp_path / "c.py"
    path.write_text(with_approval(narrowed, f"# pcat-allow: PC100 #{hash_of(narrowed)} -- {REASON}"))
    out = lint(str(path))
    assert out.exit_code == 0 and "[approved (confirmed):" in out.output
    assert "no base ref: approvals treated as confirmed" in out.output


def test_hash_mismatch_is_stale_and_approves_nothing(tmp_path, narrowed):
    old = hash_of(narrowed)
    changed = narrowed.replace("attempts < 1", "attempts < 2")
    path = tmp_path / "c.py"
    path.write_text(with_approval(changed, f"# pcat-allow: PC100 #{old} -- {REASON}"))
    out = lint(str(path))
    assert out.exit_code == 1
    assert f"stale approval: PC100 #{old} in `fetch` was given for different code" in out.output
    assert f"(the function's hash is now #{hash_of(changed)})" in out.output
    data = lint_json(str(path))
    assert data["findings"][0]["stale_approvals"][0]["state"] == "stale"


def test_v4_format_is_stale_with_the_hash_to_add(tmp_path, narrowed):
    path = tmp_path / "c.py"
    path.write_text(with_approval(narrowed, f"# pcat-allow: PC100 -- {REASON}"))
    out = lint(str(path))
    assert out.exit_code == 1
    assert (f"has no code hash (v4 format); if the current code is approved, write: "
            f"# pcat-allow: PC100 #{hash_of(narrowed)} -- {REASON}") in out.output


def test_lint_shows_the_hash_next_to_every_deviation(tmp_path, narrowed):
    path = tmp_path / "c.py"
    path.write_text(narrowed)
    h = hash_of(narrowed)
    out = lint(str(path))
    assert f"PC100 high #{h}: " in out.output
    assert all(d["hash"] == h for f in lint_json(str(path))["findings"] for d in f["deviations"])
    assert f"[hash #{h}]" in lint(str(path), "--format", "github").output


def test_check_code_shows_hash_and_template(narrowed):
    result = CatalogService(REPO_ROOT).check_code(narrowed)
    [analysis] = result["deviations"]
    h = hash_of(narrowed)
    assert analysis["hash"] == h and analysis["approval_template"] == f"# pcat-allow: <code> #{h} -- <reason>"
    assert all(d["hash"] == h for d in analysis["deviations"])
