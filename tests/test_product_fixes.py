"""v6 Part E: regression tests for the product-facing fixes from KNOWN_GAPS."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from conftest import REPO_ROOT, edit_yaml, pattern_dir
from pcat import codeunit, lint, provenance
from pcat.cli import app
from pcat.errors import CatalogError
from pcat.serving import CatalogService

HTTP = "http.get_with_retry.requests"


def test_marker_between_decorators_and_def_is_read(tmp_path):
    """v5.2: an agent wrote `@require_setting(...)`, `@login_required`, then the marker,
    then `def`; the marker was ignored and the function was only inferred."""
    src = ("@cache\n@retry(3)\n# pcat: http.get_with_retry.requests@v1\n"
           "def fetch(url):\n    return url\n")
    [info] = provenance.functions(src)
    assert info.marker is not None and info.marker.ref == "http.get_with_retry.requests@v1"
    code = CatalogService(REPO_ROOT).get_pattern(HTTP, {"f0": "fetch"})["code"]
    moved = code.replace("# pcat: http.get_with_retry.requests@v1\ndef fetch(",
                         "@staticmethod_like\n# pcat: http.get_with_retry.requests@v1\ndef fetch(")
    assert moved != code
    path = tmp_path / "client.py"
    path.write_text(moved.replace("except (requests.ConnectionError, requests.Timeout):", "except requests.Timeout:"))
    report = lint.lint_paths([str(path)], REPO_ROOT, include_inferred=False)
    [f] = report.findings
    assert f.provenance == "marked" and report.failed


def test_approval_in_the_decorator_block_counts_too():
    src = ("@cache\n# pcat-allow: PC100 #0123abcd -- explained here\n# pcat: http.get_with_retry.requests@v1\n"
           "def fetch(url):\n    return url\n")
    [info] = provenance.functions(src)
    assert [a.code for a in info.approvals] == ["PC100"] and info.marker is not None


def test_catalog_with_unknown_metadata_is_refused(root):
    edit_yaml(pattern_dir(root, HTTP), retry_budget="from a newer pcat")
    with pytest.raises(CatalogError, match=r"does not know .*retry_budget.*upgrade pcat"):
        lint.Catalog(root)
    with pytest.raises(CatalogError, match="upgrade pcat"):
        CatalogService(root)
    r = CliRunner().invoke(app, ["lint", str(root), "--catalog", str(root)])
    assert r.exit_code == 1 and "upgrade pcat" in r.output


def test_unknown_guard_keys_are_refused_too(root):
    import yaml

    path = pattern_dir(root, HTTP) / "pattern.yaml"
    data = yaml.safe_load(path.read_text())
    data["guards"][0]["severity"] = "low"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    with pytest.raises(CatalogError, match=r"guards\[0\]\.severity"):
        lint.Catalog(root)


def test_invalid_but_known_metadata_still_reports_normally(root):
    edit_yaml(pattern_dir(root, HTTP), version="one")  # a known key with a bad value: validate's job
    lint.Catalog(root)  # not refused


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    return path


def test_module_path_for_src_layout_and_namespace_packages(tmp_path):
    proj = tmp_path / "proj"
    touch(proj / "pyproject.toml")
    touch(proj / "src" / "pkg" / "__init__.py")
    assert codeunit.module_for_path(touch(proj / "src" / "pkg" / "mod.py")) == "pkg.mod"
    touch(proj / "src" / "ns" / "inner" / "__init__.py")  # `ns` has no __init__.py: a namespace package
    assert codeunit.module_for_path(touch(proj / "src" / "ns" / "inner" / "views.py")) == "ns.inner.views"
    flat = tmp_path / "flat"
    (flat / ".git").mkdir(parents=True)
    touch(flat / "company" / "auth" / "__init__.py")
    assert codeunit.module_for_path(touch(flat / "company" / "auth" / "keys.py")) == "company.auth.keys"
    assert codeunit.module_for_path(touch(tmp_path / "loose" / "tool.py")) == "tool"  # no project: unchanged
