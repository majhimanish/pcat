"""`pcat audit` (v6 Part C): a one-time, human-reviewed report; never a gate."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from conftest import REPO_ROOT
from pcat import audit, lint
from pcat.cli import app
from pcat.serving import CatalogService

HTTP = "http.get_with_retry.requests"
NARROW = ("except (requests.ConnectionError, requests.Timeout):", "except requests.Timeout:")


def unmarked(code: str) -> str:
    return code.replace("# pcat: http.get_with_retry.requests@v1\n", "")


def make_repo(tmp_path: Path) -> Path:
    code = CatalogService(REPO_ROOT).get_pattern(HTTP, {"f0": "fetch"})["code"]
    repo = tmp_path / "repo"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "client.py").write_text(unmarked(code).replace(*NARROW))  # copied, guard broken
    (repo / "app" / "ok.py").write_text(unmarked(code))  # copied, guards hold
    (repo / "app" / "marked.py").write_text(code.replace(*NARROW))  # marked: lint's job
    (repo / "app" / "other.py").write_text("def add(a, b):\n    return a + b\n")
    return repo


def test_audit_finds_copied_code_that_breaks_a_guard(tmp_path):
    report = audit.audit([str(make_repo(tmp_path))], REPO_ROOT)
    s = report["summary"]
    assert s["marked_functions_skipped"] >= 1 and s["findings"] == 1
    [f] = report["findings"]
    assert (f["path"], f["function"], f["pattern"]) == ("app/client.py", "fetch", "http.get_with_retry.requests@v1")
    assert f["similarity"] >= lint.INFERRED_GUARD_SIMILARITY and f["second_pattern"] and 0 < f["margin"] <= 1
    assert [g["kind"] for g in f["guards"]] == ["must_catch"]
    assert "no longer handles `requests.ConnectionError`" in f["guards"][0]["message"]
    assert "not confirmed bugs" in report["note"]


def test_nothing_below_the_threshold(tmp_path):
    report = audit.audit([str(make_repo(tmp_path))], REPO_ROOT, threshold=1.01)
    assert report["findings"] == [] and report["summary"]["functions_resembling_a_pattern"] == 0


def test_report_is_deterministic_and_shows_the_margin(tmp_path):
    repo = make_repo(tmp_path)
    a = audit.write(audit.audit([str(repo)], REPO_ROOT), tmp_path / "a")
    b = audit.write(audit.audit([str(repo)], REPO_ROOT), tmp_path / "b")
    assert a[0].read_bytes() == b[0].read_bytes() and a[1].read_bytes() == b[1].read_bytes()
    page = a[1].read_text()
    assert "margin" in page and "name=\"viewport\"" in page and "<script" not in page
    assert str(tmp_path) not in a[0].read_text()  # relative paths only
    assert json.loads(a[0].read_text())["findings"][0]["margin"] > 0


def test_cli_exits_zero_with_findings(tmp_path):
    repo = make_repo(tmp_path)
    out = tmp_path / "out"
    r = CliRunner().invoke(app, ["audit", str(repo), "--catalog", str(REPO_ROOT), "--out", str(out)])
    assert r.exit_code == 0, r.output
    assert "1 finding(s)" in r.output and (out / "audit.html").exists() and (out / "audit.json").exists()
