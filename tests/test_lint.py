"""`pcat lint` (v4 Part D): exit codes, approvals, inferred provenance, --changed-since, formats."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from conftest import REPO_ROOT
from pcat import lint
from pcat.cli import app
from pcat.serving import CatalogService

HTTP = "http.get_with_retry.requests"


@pytest.fixture(scope="module")
def http_code() -> str:
    return CatalogService(REPO_ROOT).get_pattern(HTTP, {"f0": "fetch"})["code"]


NARROW = ("except (requests.ConnectionError, requests.Timeout):", "except requests.Timeout:")


def write(tmp_path: Path, code: str, name: str = "client.py") -> Path:
    path = tmp_path / name
    path.write_text(code)
    return path


def run(*args: str):
    return CliRunner().invoke(app, ["lint", *args, "--catalog", str(REPO_ROOT)])


def as_json(*args: str) -> dict:
    out = run(*args, "--format", "json")
    return json.loads(out.output)


def test_clean_marked_code_passes(tmp_path, http_code):
    path = write(tmp_path, http_code)
    out = run(str(path))
    assert out.exit_code == 0, out.output
    assert "fetch <- http.get_with_retry.requests@v1 get_with_retry (marked)" in out.output
    assert "no deviations" in out.output


def test_high_deviation_fails_by_default_and_never_disables(tmp_path, http_code):
    path = write(tmp_path, http_code.replace(*NARROW))
    out = run(str(path))
    assert out.exit_code == 1
    assert "PC100 high" in out.output and "[fails]" in out.output
    assert "-        except (requests.ConnectionError, requests.Timeout):" in out.output  # the diff
    assert run(str(path), "--fail-on", "never").exit_code == 0


def test_fail_on_levels(tmp_path, http_code):
    # v4.1: dropping 429 is now a guard violation (must_include), so use another low change
    low = http_code.replace("base_delay: float=0.5", "base_delay: float=1.0")
    assert low != http_code
    lp = write(tmp_path, low, "low.py")
    assert run(str(lp)).exit_code == 0
    assert run(str(lp), "--fail-on", "medium").exit_code == 0
    assert run(str(lp), "--fail-on", "low").exit_code == 1
    private = http_code.replace("hint = retry_after_seconds(response.headers.get('Retry-After'))",
                                "hint = retry_after_seconds(response._headers.get('Retry-After'))")
    mp = write(tmp_path, private, "medium.py")
    data = as_json(str(mp))
    assert [d["code"] for f in data["findings"] for d in f["deviations"]] == ["PC106"]
    assert run(str(mp)).exit_code == 0 and run(str(mp), "--fail-on", "medium").exit_code == 1


def approve(code: str, line: str) -> str:
    return code.replace("# pcat: http.get_with_retry.requests@v1\ndef fetch(",
                        f"{line}\n# pcat: http.get_with_retry.requests@v1\ndef fetch(")


def fetch_hash(code: str) -> str:
    """v4.1: the current hash of `fetch`, as approvals must carry it."""
    import ast

    from pcat import provenance

    node = next(n for n in ast.parse(code).body if isinstance(n, ast.FunctionDef) and n.name == "fetch")
    return provenance.function_hash(node)


def test_valid_approval_passes_and_is_reported(tmp_path, http_code):
    reason = "this API only treats timeouts as transient; connection errors must fail fast"
    code = http_code.replace(*NARROW)
    path = write(tmp_path, approve(code, f"# pcat-allow: PC100 #{fetch_hash(code)} -- {reason}"))
    out = run(str(path))
    assert out.exit_code == 0, out.output
    assert f"[approved (confirmed): {reason}]" in out.output  # v4.1: state shown; no base = confirmed
    dev = as_json(str(path))["findings"][0]["deviations"][0]
    assert dev["approved"] and dev["approval"] == reason and dev["code"] == "PC100"


@pytest.mark.parametrize("line,warning", [
    ("# pcat-allow: PC100", "approval has no reason"),
    ("# pcat-allow: PC100 -- too short", "shorter than 10 characters"),
    ("# pcat-allow: PC100 PC101 -- two codes are not allowed here", "malformed approval"),
])
def test_invalid_approvals_do_not_count(tmp_path, http_code, line, warning):
    path = write(tmp_path, approve(http_code.replace(*NARROW), line))
    out = run(str(path))
    assert out.exit_code == 1 and warning in out.output


def test_stale_approval_is_a_warning(tmp_path, http_code):
    path = write(tmp_path, approve(http_code, f"# pcat-allow: PC101 #{fetch_hash(http_code)} -- "
                                              "kept from an older version of this code"))
    out = run(str(path))
    assert out.exit_code == 0
    assert "warning: stale approval: PC101 no longer occurs in `fetch`" in out.output
    assert as_json(str(path))["findings"][0]["stale_approvals"][0]["code"] == "PC101"


def test_inferred_provenance_never_fails(tmp_path, http_code):
    unmarked = http_code.replace("# pcat: http.get_with_retry.requests@v1\n", "").replace(*NARROW)
    path = write(tmp_path, unmarked)
    out = run(str(path))  # text: inferred on by default
    assert out.exit_code == 0
    assert "(inferred, similarity" in out.output and "PC100 high" in out.output
    data = as_json(str(path))  # json: inferred off by default
    assert data["findings"] == []
    data = as_json(str(path), "--include-inferred")
    assert data["findings"][0]["provenance"] == "inferred" and not data["failed"]
    assert run(str(path), "--no-include-inferred").output.startswith("0 function(s) checked")


def test_unknown_pattern_marker_is_an_error(tmp_path):
    path = write(tmp_path, "# pcat: nope.nothing@v1\ndef f():\n    return 1\n")
    out = run(str(path))
    assert out.exit_code == 1 and "unknown pattern nope.nothing@v1" in out.output


def test_github_format(tmp_path, http_code):
    reason = "documented reason for the low change here"
    code = http_code.replace(*NARROW).replace("base_delay: float=0.5", "base_delay: float=1.0")  # v4.1: low change
    path = write(tmp_path, approve(code, f"# pcat-allow: PC109 #{fetch_hash(code)} -- {reason}"))
    out = run(str(path), "--format", "github")
    lines = out.output.splitlines()
    assert out.exit_code == 1
    assert lines[0].startswith(f"::error file={path.as_posix().replace(':', '%3A')},line=")
    assert "title=PC100 guard violated (high) - http.get_with_retry.requests@v1::" in lines[0]
    assert lines[1].startswith("::notice ") and f"(approved, confirmed: {reason})" in lines[1]


def test_github_escaping():
    assert lint._gh_escape("a%b\nc") == "a%25b%0Ac"
    assert lint._gh_escape("x:y,z", prop=True) == "x%3Ay%2Cz"


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                   cwd=cwd, check=True, capture_output=True)


def test_changed_since_only_checks_touched_functions(tmp_path, http_code):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    pbkdf2 = CatalogService(REPO_ROOT).get_pattern("auth.password.pbkdf2")["code"]
    write(repo, http_code.replace(*NARROW), "net.py")  # violation committed before REF
    write(repo, pbkdf2, "pw.py")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    old = (repo / "pw.py").read_text()
    (repo / "pw.py").write_text(old.replace("return hmac.compare_digest(key, expected)",
                                            "return key == expected"))
    write(repo, "# pcat: auth.password.pbkdf2@v1\ndef extra(p):\n    return p\n", "new.py")  # untracked
    data = as_json(str(repo), "--changed-since", "HEAD")
    checked = sorted((f["path"].split("/")[-1], f["function"]) for f in data["findings"])
    assert checked == [("new.py", "extra"), ("pw.py", "verify_password")]
    everything = as_json(str(repo))
    assert {f["path"].split("/")[-1] for f in everything["findings"]} == {"net.py", "pw.py", "new.py"}


def test_parse_diff_lines():
    diff = "@@ -3,0 +4,2 @@\n+a\n+b\n@@ -10 +12 @@\n-x\n+y\n@@ -20,3 +21,0 @@\n"
    assert lint.parse_diff_lines(diff) == {4, 5, 12, 21}


def test_report_is_deterministic(tmp_path, http_code):
    write(tmp_path, http_code.replace(*NARROW), "b.py")
    write(tmp_path, http_code, "a.py")
    first, second = as_json(str(tmp_path)), as_json(str(tmp_path))
    assert first == second and [f["path"].split("/")[-1] for f in first["findings"]] == ["a.py", "b.py"]
