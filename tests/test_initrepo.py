"""`pcat init` (v6 Part D): dry run, apply, idempotence, detection, CI fallback."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pcat import initrepo, starter
from pcat.cli import app

APP = '''\
from {fw} import thing


def handler(request):
    return thing(request)
'''


def make_repo(tmp_path: Path, framework: str = "fastapi", ci: str = "github", git: bool = True) -> Path:
    repo = tmp_path / "repo"
    (repo / "app").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    for i in range(3):
        (repo / "app" / f"m{i}.py").write_text(APP.format(fw=framework) if framework != "none" else "x = 1\n")
    if ci == "github":
        (repo / ".github" / "workflows").mkdir(parents=True)
    elif ci == "gitlab":
        (repo / ".gitlab-ci.yml").write_text("test:\n  script: pytest\n")
    if git:
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo


def snapshot(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and ".git" not in p.relative_to(root).parts}


def run(args, cwd=None):
    old = os.getcwd()
    try:
        if cwd:
            os.chdir(cwd)
        return CliRunner().invoke(app, args)
    finally:
        os.chdir(old)


def test_dry_run_changes_nothing(tmp_path):
    repo = make_repo(tmp_path)
    before = snapshot(repo)
    r = run(["init", "--path", str(repo), "--starter"])
    assert r.exit_code == 0, r.output
    assert snapshot(repo) == before
    assert "would create .mcp.json" in r.output and "dry run: nothing was changed" in r.output


def test_apply_creates_the_files_and_a_second_run_is_a_no_op(tmp_path):
    repo = make_repo(tmp_path)
    r = run(["init", "--path", str(repo), "--starter", "--apply"])
    assert r.exit_code == 0, r.output
    for rel in (".pcat/config.yaml", ".pcat/approvers.yaml", ".mcp.json", ".claude/settings.json", "CLAUDE.md",
                ".github/workflows/pcat-lint.yml", ".github/workflows/pcat-approvals.yml",
                "pcat-catalog/catalog/index.json", ".pcat/candidates.md", ".pcat/mining/report.json"):
        assert (repo / rel).is_file(), rel
    patterns = sorted(p.parent.name for p in (repo / "pcat-catalog" / "catalog").rglob("pattern.yaml"))
    assert len(patterns) == len(starter.PATTERN_IDS)
    mcp = json.loads((repo / ".mcp.json").read_text())["mcpServers"]["pcat"]
    assert mcp["command"] == "pcat" and mcp["args"][:2] == ["serve", "--catalog"]
    assert mcp["args"][2] == "${CLAUDE_PROJECT_DIR:-.}/pcat-catalog"
    lint_wf = (repo / ".github/workflows/pcat-lint.yml").read_text()
    assert "--changed-since" in lint_wf and "--fail-on high" in lint_wf and "--include-inferred" not in lint_wf
    assert "next steps:" in r.output and "1. Review .pcat/candidates.md" in r.output
    after = snapshot(repo)
    again = run(["init", "--path", str(repo), "--starter", "--apply"])
    assert again.exit_code == 0 and "nothing to change" in again.output and "(unchanged)" in again.output
    assert snapshot(repo) == after


def test_existing_files_are_merged_not_replaced(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "CLAUDE.md").write_text("# Rules\nUse tabs.")
    (repo / ".mcp.json").write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
    p = initrepo.plan(repo)
    initrepo.apply(p)
    assert (repo / "CLAUDE.md").read_text() == "# Rules\nUse tabs.\n\n" + initrepo.CLAUDE_NOTE + "\n"
    assert set(json.loads((repo / ".mcp.json").read_text())["mcpServers"]) == {"other", "pcat"}
    assert initrepo.plan(repo).changes == []


@pytest.mark.parametrize("framework", ["fastapi", "django", "flask", "none"])
def test_framework_detection(tmp_path, framework):
    assert initrepo.detect(make_repo(tmp_path, framework))["framework"] == framework


def test_other_ci_gets_instructions_not_workflows(tmp_path):
    repo = make_repo(tmp_path, ci="gitlab")
    p = initrepo.plan(repo)
    assert p.facts["ci"] == "gitlab"
    assert not any(c.path.startswith(".github/") for c in p.changes)
    assert any("not set up automatically" in n and "pcat lint" in n for n in p.notes)
    r = run(["init", "--path", str(repo)])
    assert "note: CI provider 'gitlab'" in r.output


def test_existing_catalog_and_config_lookup(tmp_path):
    repo = make_repo(tmp_path)
    initrepo.apply(initrepo.plan(repo, starter_catalog=True))
    moved = repo / "patterns"
    (repo / "pcat-catalog").rename(moved)
    p = initrepo.plan(repo, catalog=moved)
    assert p.catalog_rel == "patterns" and p.seed == "existing"
    initrepo.apply(p)
    assert "catalog: patterns" in (repo / ".pcat" / "config.yaml").read_text()
    r = run(["show", "auth.password.pbkdf2"], cwd=repo / "app")  # catalog found through .pcat/config.yaml
    assert r.exit_code == 0 and "auth.password.pbkdf2" in r.output


def test_empty_catalog_by_default_and_errors(tmp_path):
    repo = make_repo(tmp_path, git=False)
    p = initrepo.plan(repo)
    assert p.seed == "empty" and not p.facts["git"]
    initrepo.apply(p)
    assert json.loads((repo / "pcat-catalog/catalog/index.json").read_text())["patterns"] == []
    r = run(["init", "--path", str(repo), "--catalog", str(repo), "--starter"])
    assert r.exit_code == 1 and "alternatives" in r.output
