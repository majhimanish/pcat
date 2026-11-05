"""`pcat init`: set pcat up in a repository (v6 Part D).

Plans every file it would create or change, with a reason; nothing is written unless
`apply=True`. Each planned file is compared with what is already there, so a second run
plans nothing. Mining runs only on apply and writes deterministic output, so it is a no-op
the second time too.

Claude Code MCP configuration follows https://code.claude.com/docs/en/mcp ("Project
scope"): a `.mcp.json` at the project root, `{"mcpServers": {name: {"type": "stdio",
"command", "args", "env"}}}` (the format `claude mcp add --scope project` writes). The
working directory of a stdio server is not guaranteed, so paths use
`${CLAUDE_PROJECT_DIR:-.}`, which the docs allow in project-scoped `args`. Interactive
sessions ask once to approve a project server; `enabledMcpjsonServers` in the project's
`.claude/settings.json` approves it in a trusted folder, and `claude -p` loads it without
asking.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from pcat import catalog as cat
from pcat import starter
from pcat.errors import PcatError

CONFIG = Path(".pcat") / "config.yaml"
APPROVERS = Path(".pcat") / "approvers.yaml"
DEFAULT_CATALOG = "pcat-catalog"
CLAUDE_NOTE = "This repo uses the organization's pattern catalog via the pcat tools."  # tested in v5
PCAT_INSTALL = 'pip install "pcat[mcp] @ git+https://github.com/majhimanish/pcat"'
FRAMEWORKS = ("fastapi", "django", "flask")
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "build", "dist", ".tox", DEFAULT_CATALOG}


@dataclass
class Change:
    path: str  # relative to the repository
    action: str  # create | update
    reason: str
    content: str | None = None  # None: a directory or a copied tree
    copy_from: Path | None = None


@dataclass
class Plan:
    repo: Path
    facts: dict
    changes: list[Change] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    catalog_rel: str = DEFAULT_CATALOG
    seed: str = "empty"  # starter | existing | empty


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #


def _python_files(repo: Path, limit: int = 5000) -> list[Path]:
    out = []
    for path in sorted(repo.rglob("*.py")):
        if any(part in SKIP_DIRS or part.startswith(".") for part in path.relative_to(repo).parts[:-1]):
            continue
        out.append(path)
        if len(out) >= limit:
            break
    return out


def detect(repo: Path) -> dict:
    """Python project?, main framework, git repo?, CI provider."""
    py = _python_files(repo)
    markers = [n for n in ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile")
               if (repo / n).exists()]
    counts = {f: 0 for f in FRAMEWORKS}
    imp = re.compile(r"^\s*(?:from|import)\s+(fastapi|django|flask)\b", re.MULTILINE)
    for path in py:
        try:
            for m in imp.finditer(path.read_text(encoding="utf-8", errors="replace")):
                counts[m.group(1)] += 1
        except OSError:
            continue
    framework = max(FRAMEWORKS, key=lambda f: (counts[f], -FRAMEWORKS.index(f))) if any(counts.values()) else "none"
    if (repo / ".github" / "workflows").is_dir() or (repo / ".github").is_dir():
        ci = "github"
    elif (repo / ".gitlab-ci.yml").exists():
        ci = "gitlab"
    elif (repo / ".circleci").is_dir():
        ci = "circleci"
    elif (repo / "Jenkinsfile").exists():
        ci = "jenkins"
    elif (repo / "azure-pipelines.yml").exists():
        ci = "azure"
    else:
        ci = "github" if "github.com" in _git(repo, "remote", "-v") else "none"
    return {"python": bool(py or markers), "python_files": len(py), "framework": framework,
            "framework_imports": counts, "git": (repo / ".git").exists() or bool(_git(repo, "rev-parse", "--git-dir")),
            "ci": ci, "default_branch": _default_branch(repo)}


def _git(repo: Path, *args: str) -> str:
    try:
        proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout if proc.returncode == 0 else ""


def _default_branch(repo: Path) -> str:
    head = _git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip()
    if head.startswith("origin/"):
        return head.split("/", 1)[1]
    current = _git(repo, "branch", "--show-current").strip()
    return current if current in ("main", "master") else "main"


# --------------------------------------------------------------------------- #
# Planning
# --------------------------------------------------------------------------- #


def _want(plan: Plan, rel: str, content: str, reason: str) -> None:
    path = plan.repo / rel
    if path.exists():
        if path.read_text(encoding="utf-8") == content:
            return
        plan.changes.append(Change(rel, "update", reason, content))
    else:
        plan.changes.append(Change(rel, "create", reason, content))


def config_text(catalog_rel: str, branch: str) -> str:
    return (f"# pcat settings for this repository (written by `pcat init`).\n"
            f"# catalog: the folder that holds catalog/ (relative to the repository root).\n"
            f"catalog: {catalog_rel}\n"
            f"approvers: {APPROVERS.as_posix()}\n"
            f"lint:\n"
            f"  # v5.1 recommendation: only marked code fails, on high-severity deviations\n"
            f"  # of functions changed since the base branch; inferred findings stay advisory.\n"
            f"  base: origin/{branch}\n"
            f"  fail_on: high\n"
            f"  include_inferred: false\n")


APPROVERS_TEXT = """\
# Who may confirm proposed `# pcat-allow: PCxxx #<hash> -- reason` approvals in pull
# requests. Fill in GitHub usernames; until then, proposals cannot be confirmed.
approvers: []          # e.g. [alice, bob]
codeowners: true       # also anyone CODEOWNERS lists for the changed file (users, not teams)
allow_author: false    # true lets authors confirm their own proposals (solo work only)
"""


def mcp_text(existing: str | None, catalog_rel: str) -> str:
    data = json.loads(existing) if existing and existing.strip() else {}
    if not isinstance(data, dict):
        raise PcatError(".mcp.json is not a JSON object")
    servers = data.setdefault("mcpServers", {})
    servers["pcat"] = {"type": "stdio", "command": "pcat",
                       "args": ["serve", "--catalog", f"${{CLAUDE_PROJECT_DIR:-.}}/{catalog_rel}",
                                "--repo", "${CLAUDE_PROJECT_DIR:-.}"], "env": {}}
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def claude_settings_text(existing: str | None) -> str:
    data = json.loads(existing) if existing and existing.strip() else {}
    if not isinstance(data, dict):
        raise PcatError(".claude/settings.json is not a JSON object")
    enabled = data.setdefault("enabledMcpjsonServers", [])
    if "pcat" not in enabled:
        enabled.append("pcat")
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def claude_md_text(existing: str | None) -> str:
    text = existing or ""
    if CLAUDE_NOTE in text:
        return text
    return text + ("\n" if text and not text.endswith("\n") else "") + ("\n" if text.strip() else "") + CLAUDE_NOTE + "\n"


def lint_workflow(catalog_rel: str) -> str:
    return f"""\
# pcat lint on pull requests (written by `pcat init`). v5.1 recommendation: only code
# marked `# pcat: <id>@vN` fails, on unapproved high-severity deviations of functions the
# pull request changed; findings on unmarked code are advisory annotations.
name: pcat-lint

on:
  pull_request:

permissions:
  contents: read

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # --changed-since needs the base commit
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: {PCAT_INSTALL}
      - name: pcat lint
        run: >-
          pcat lint . --catalog {catalog_rel} --format github --fail-on high
          --changed-since "origin/${{{{ github.base_ref }}}}"
"""


def approvals_workflow(catalog_rel: str) -> str:
    return f"""\
# Fails a pull request while a proposed `# pcat-allow` approval is unconfirmed (written by
# `pcat init`). Approvers (.pcat/approvers.yaml) confirm with an approving review of the
# latest commit or a "/pcat approve" comment. Keep this file name: the re-run step uses it.
name: pcat-approvals

on:
  pull_request:
    types: [opened, synchronize, reopened]
  pull_request_review:
    types: [submitted, dismissed]
  issue_comment:
    types: [created, edited]

permissions:
  contents: read
  pull-requests: read
  issues: read
  actions: write  # to re-run the pull_request check once a review or comment confirms

concurrency:
  group: pcat-approvals-${{{{ github.event.pull_request.number || github.event.issue.number }}}}
  cancel-in-progress: false

jobs:
  approvals:
    if: >-
      github.event_name != 'issue_comment' ||
      (github.event.issue.pull_request && contains(github.event.comment.body, '/pcat approve'))
    runs-on: ubuntu-latest
    env:
      PR: ${{{{ github.event.pull_request.number || github.event.issue.number }}}}
    steps:
      - uses: actions/checkout@v4
        with:
          ref: refs/pull/${{{{ github.event.pull_request.number || github.event.issue.number }}}}/head
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: {PCAT_INSTALL}
      - name: pcat approvals check
        env:
          GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
        run: pcat approvals check --repo "${{{{ github.repository }}}}" --pr "$PR" --catalog {catalog_rel}
      - name: Re-run the pull request check
        if: success() && github.event_name != 'pull_request'
        env:
          GH_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
        run: |
          sha=$(gh api "repos/${{{{ github.repository }}}}/pulls/$PR" --jq .head.sha)
          for id in $(gh run list --repo "${{{{ github.repository }}}}" --workflow pcat-approvals.yml \\
                        --event pull_request --commit "$sha" --json databaseId,conclusion \\
                        --jq '.[] | select(.conclusion == "failure") | .databaseId'); do
            gh run rerun "$id" --failed --repo "${{{{ github.repository }}}}"
          done
"""


def ci_instructions(ci: str, catalog_rel: str) -> str:
    return (f"CI provider '{ci}' is not set up automatically. Add two steps to pull-request builds "
            f"(fetch the full history first):\n"
            f"  {PCAT_INSTALL}\n"
            f"  pcat lint . --catalog {catalog_rel} --fail-on high --changed-since origin/<target-branch>\n"
            f"  pcat approvals check --repo <owner/repo> --pr <number> --catalog {catalog_rel}   "
            f"# needs GITHUB_TOKEN; GitHub-hosted pull requests only")


def plan(repo: Path, catalog: Path | None = None, starter_catalog: bool = False) -> Plan:
    repo = Path(repo).resolve()
    if not repo.is_dir():
        raise PcatError(f"{repo} is not a directory")
    if catalog is not None and starter_catalog:
        raise PcatError("--catalog and --starter are alternatives; pass one")
    facts = detect(repo)
    p = Plan(repo, facts)
    existing_config = _read_config(repo)
    if catalog is not None:
        root = Path(catalog).resolve()
        root = root.parent if root.name == cat.CATALOG_DIR and root.is_dir() else root
        if not (root / cat.CATALOG_DIR).is_dir():
            raise PcatError(f"no {cat.CATALOG_DIR}/ under {root}")
        try:
            p.catalog_rel = root.relative_to(repo).as_posix()
        except ValueError:
            p.catalog_rel = root.as_posix()
            p.notes.append(f"the catalog {root} is outside the repository: CI and other machines need "
                           f"it at the same path (or point `catalog:` in {CONFIG} elsewhere)")
        p.seed = "existing"
    elif existing_config.get("catalog"):
        p.catalog_rel = str(existing_config["catalog"])
        p.seed = "existing" if (repo / p.catalog_rel / cat.CATALOG_DIR).is_dir() else ("starter" if starter_catalog else "empty")
    else:
        p.seed = "starter" if starter_catalog else "empty"
    if p.seed != "existing" and not (repo / p.catalog_rel / cat.CATALOG_DIR).is_dir():
        if p.seed == "starter":
            p.changes.append(Change(f"{p.catalog_rel}/{cat.CATALOG_DIR}", "create",
                                    f"catalog seeded with the {len(starter.PATTERN_IDS)} starter patterns",
                                    copy_from=starter.catalog_root() / cat.CATALOG_DIR))
        else:
            p.changes.append(Change(f"{p.catalog_rel}/{cat.CATALOG_DIR}", "create",
                                    "an empty catalog (promote patterns into it, or rerun with --starter)"))
    _want(p, CONFIG.as_posix(), config_text(p.catalog_rel, facts["default_branch"]),
          "catalog location, approvers file and lint settings")
    if not (repo / APPROVERS).exists():
        _want(p, APPROVERS.as_posix(), APPROVERS_TEXT, "who may confirm proposed approvals (template)")
    mcp = repo / ".mcp.json"
    _want(p, ".mcp.json", mcp_text(mcp.read_text(encoding="utf-8") if mcp.exists() else None, p.catalog_rel),
          "Claude Code project MCP server: `pcat serve` with this catalog")
    settings = repo / ".claude" / "settings.json"
    _want(p, ".claude/settings.json",
          claude_settings_text(settings.read_text(encoding="utf-8") if settings.exists() else None),
          "approve the project's pcat MCP server in Claude Code (trusted folders)")
    md = repo / "CLAUDE.md"
    _want(p, "CLAUDE.md", claude_md_text(md.read_text(encoding="utf-8") if md.exists() else None),
          "one line telling coding agents to use the pcat tools")
    if facts["ci"] == "github":
        _want(p, ".github/workflows/pcat-lint.yml", lint_workflow(p.catalog_rel),
              "pull requests: pcat lint (marked code, high severity, changed functions)")
        _want(p, ".github/workflows/pcat-approvals.yml", approvals_workflow(p.catalog_rel),
              "pull requests: wait for a human to confirm proposed approvals")
    else:
        p.notes.append(ci_instructions(facts["ci"], p.catalog_rel))
    if not facts["python"]:
        p.notes.append("no Python files found: pcat checks Python code only")
    return p


def _read_config(repo: Path) -> dict:
    path = repo / CONFIG
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def load_config(start: Path) -> tuple[Path, dict] | None:
    """(repository root, .pcat/config.yaml) for the nearest parent that has one."""
    start = Path(start).resolve()
    for folder in (start, *start.parents):
        if (folder / CONFIG).is_file():
            return folder, _read_config(folder)
    return None


# --------------------------------------------------------------------------- #
# Applying
# --------------------------------------------------------------------------- #


def apply(p: Plan) -> list[str]:
    done = []
    for ch in p.changes:
        target = p.repo / ch.path
        if ch.copy_from is not None:
            shutil.copytree(ch.copy_from, target, ignore=shutil.ignore_patterns("__pycache__"))
            cat.write_index(target.parent)
        elif ch.content is None:
            target.mkdir(parents=True, exist_ok=True)
            cat.write_index(target.parent)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(ch.content, encoding="utf-8")
        done.append(f"{ch.action}d {ch.path}")
    return done


MINE_DIR = Path(".pcat") / "mining"


def mine_candidates(p: Plan, top: int = 10) -> tuple[str, list[str]]:
    """Mine the repository; write .pcat/mining/report.{json,html} and .pcat/candidates.md.
    Returns (summary line, written paths that changed)."""
    from pcat import miner

    catalog_root = p.repo / p.catalog_rel
    settings = miner.MineSettings(excludes=(f"{p.catalog_rel}/*",))
    result = miner.mine([str(p.repo)], settings, jobs=1, cache_dir=None,
                        catalog_root=catalog_root if (catalog_root / cat.CATALOG_DIR).is_dir() else None)
    before = {f: (p.repo / f).read_bytes() for f in (MINE_DIR / "report.json", MINE_DIR / "report.html")
              if (p.repo / f).exists()}
    # The report names the input by absolute path and git commit; here that would change on
    # every commit and break "a second run changes nothing", so the input is just ".".
    result.report["inputs"] = [{"path": "."}]
    miner.write_report(result.report, p.repo / MINE_DIR)
    clusters = result.report.get("function_clusters", [])[:top]
    lines = ["# pcat candidates", "",
             "Repeated function shapes in this repository (from `pcat mine`). Each is a candidate for a",
             "reviewed pattern: look at the members in `.pcat/mining/report.html`, pick the best one and run",
             "the command shown (then write tests and open a pull request).", ""]
    if not clusters:
        lines.append("No repeated shapes found. Start from the starter catalog (`pcat init --starter`) or add "
                     "a pattern by hand with `pcat add`.")
    for c in clusters:
        lines.append(f"- `{c['id']}`: {c['occurrences']} similar functions, e.g. "
                     f"`{c['members'][0]['path']}:{c['members'][0]['qualname']}`")
        lines.append(f"  `pcat --root {p.catalog_rel} promote {c['id']} --report {MINE_DIR.as_posix()}/report.json "
                     f"--id <category>.<name>`")
    text = "\n".join(lines) + "\n"
    changed = [f.as_posix() for f in (MINE_DIR / "report.json", MINE_DIR / "report.html")
               if before.get(f) != (p.repo / f).read_bytes()]
    cand = p.repo / ".pcat" / "candidates.md"
    if not cand.exists() or cand.read_text(encoding="utf-8") != text:
        cand.write_text(text, encoding="utf-8")
        changed.append(".pcat/candidates.md")
    stats = result.report["stats"]
    return (f"mined {stats['functions_mined']} function(s): {stats['function_clusters']} repeated shape(s); "
            f"candidates in .pcat/candidates.md"), changed


def next_steps(p: Plan) -> list[str]:
    steps = ["Review .pcat/candidates.md and promote one or two patterns (`pcat promote …`), with tests.",
             f"Add approvers to {APPROVERS.as_posix()} (GitHub usernames).",
             "Commit the new files and open a pull request so the team reviews the setup."]
    if p.facts["ci"] == "github":
        steps += ["Protect the default branch, and make the `pcat-lint` and `pcat-approvals` checks required.",
                  "In Claude Code, open the repository once and approve the `pcat` MCP server if asked."]
    else:
        steps += ["Add the pcat steps printed above to your CI and make them required."]
    steps.append("Run `pcat audit .` once and review its findings.")
    return steps


def format_plan(p: Plan, applied: bool) -> str:
    f = p.facts
    lines = [f"repository: {p.repo}",
             f"detected: python={'yes' if f['python'] else 'no'} ({f['python_files']} files), "
             f"framework={f['framework']}, git={'yes' if f['git'] else 'no'}, CI={f['ci']}, "
             f"default branch={f['default_branch']}",
             f"catalog: {p.catalog_rel} ({p.seed})"]
    if not p.changes:
        lines.append("nothing to change: pcat is already set up here")
    for ch in p.changes:
        lines.append(f"  {'' if applied else 'would '}{ch.action} {ch.path} — {ch.reason}")
    for note in p.notes:
        lines.append(f"note: {note}")
    return "\n".join(lines)
