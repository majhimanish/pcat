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


# Part B: states against a base ref -----------------------------------------


def git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                          cwd=cwd, check=True, capture_output=True, text=True)
    return proc.stdout.strip()


def commit_file(repo: Path, text: str, message: str) -> str:
    (repo / "client.py").write_text(text)
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q")
    return path


def states(repo: Path, base: str) -> list[tuple[str, str]]:
    data = lint_json(str(repo / "client.py"), "--changed-since", base)
    return [(a["code"], a["state"]) for f in data["findings"] for a in f["approvals"]]


def test_confirmed_proposed_and_stale_against_base(repo, narrowed):
    h = hash_of(narrowed)
    approved = with_approval(narrowed, f"# pcat-allow: PC100 #{h} -- {REASON}")
    base0 = commit_file(repo, narrowed, "narrowed, no approval")
    commit_file(repo, approved, "proposal")
    assert states(repo, base0) == [("PC100", "proposed")]  # new since base: a proposal
    out = lint(str(repo / "client.py"), "--changed-since", base0)
    assert out.exit_code == 1 and "[proposed approval, needs confirmation:" in out.output
    assert "1 proposed approval(s) since" in out.output
    base1 = git(repo, "rev-parse", "HEAD")
    # same approval line already on the base ref: confirmed (a comment-only edit keeps the hash)
    commit_file(repo, approved.replace("    for attempt in", "    # one try per attempt\n    for attempt in"),
                "touch")
    assert states(repo, base1) == [("PC100", "confirmed")]
    assert lint(str(repo / "client.py"), "--changed-since", base1).exit_code == 0
    # the code changed after approval: stale
    commit_file(repo, approved.replace("attempts < 1", "attempts < 2"), "change the code")
    assert states(repo, base1) == [("PC100", "stale")]


def test_without_base_all_approvals_are_confirmed(repo, narrowed):
    commit_file(repo, with_approval(narrowed, f"# pcat-allow: PC100 #{hash_of(narrowed)} -- {REASON}"), "x")
    data = lint_json(str(repo / "client.py"))
    assert data["approval_states"] == "no base ref: approvals treated as confirmed"
    assert data["findings"][0]["approvals"][0]["state"] == "confirmed" and not data["failed"]


# Part B: the GitHub gate (fake API) -----------------------------------------


from pcat import approvals  # noqa: E402

HEAD_TIME = "2026-11-03T10:00:00Z"


def review(user, state="APPROVED", commit="HEAD", at="2026-11-03T11:00:00Z"):
    return {"user": {"login": user}, "state": state, "commit_id": commit, "submitted_at": at}


def comment(user, body="/pcat approve", at="2026-11-03T11:00:00Z"):
    return {"user": {"login": user}, "body": body, "created_at": at}


class FakeClient:
    def __init__(self, head: str, base: str, author="author", reviews=(), comments=()):
        self.data = {
            "/repos/o/r/pulls/7": {"user": {"login": author}, "head": {"sha": head}, "base": {"sha": base}},
            f"/repos/o/r/commits/{head}": {"commit": {"committer": {"date": HEAD_TIME}}},
            "/repos/o/r/pulls/7/reviews": [{**r, "commit_id": head if r["commit_id"] == "HEAD" else r["commit_id"]}
                                           for r in reviews],
            "/repos/o/r/issues/7/comments": list(comments),
        }
        self.calls = []

    def get(self, path, params=None):
        self.calls.append(path)
        return self.data[path]

    def get_all(self, path):
        return self.get(path)


@pytest.fixture
def proposal_repo(repo, narrowed, monkeypatch):
    base = commit_file(repo, narrowed, "narrowed, no approval")
    head = commit_file(repo, with_approval(narrowed, f"# pcat-allow: PC100 #{hash_of(narrowed)} -- {REASON}"),
                       "agent proposes an approval")
    monkeypatch.chdir(repo)
    return repo, base, head


def gate(proposal_repo, config, **kw):
    repo, base, head = proposal_repo
    pr = approvals.fetch_pull_request(FakeClient(head, base, **kw), "o/r", 7)
    return approvals.check(pr, ["."], REPO_ROOT, repo, config)


OWNER = approvals.Config(approvers=("owner",))


def test_unconfirmed_proposal_fails_and_says_who_may_confirm(proposal_repo):
    result = gate(proposal_repo, OWNER)
    assert result.failed and len(result.waiting) == 1 and result.waiting[0]["may_confirm"] == ["owner"]
    text = approvals.format_result(result, OWNER)
    assert "WAITING client.py:" in text and f"PC100 #" in text and "in `fetch`" in text
    assert "may confirm: @owner, by an approving review of commit" in text
    assert "or a comment containing '/pcat approve' posted after 2026-11-03 10:00:00Z" in text
    assert "1 waiting, 0 confirmed" in text and text.rstrip().endswith("FAIL")


def test_review_after_last_commit_confirms(proposal_repo):
    result = gate(proposal_repo, OWNER, reviews=[review("Owner")])
    assert not result.failed and result.confirmed[0]["confirmed_by"] == ["owner"]
    text = approvals.format_result(result, OWNER)
    assert "CONFIRMED client.py:" in text and "by @owner" in text and text.rstrip().endswith("OK")
    dev = result.report.findings[0].deviations[0]
    assert dev["approved"] and dev["approval_state"] == "proposed-confirmed"


def test_review_of_an_older_commit_does_not_count(proposal_repo):
    assert gate(proposal_repo, OWNER, reviews=[review("owner", commit="0" * 40)]).failed


def test_later_changes_requested_cancels_approval(proposal_repo):
    result = gate(proposal_repo, OWNER, reviews=[review("owner"), review("owner", "CHANGES_REQUESTED",
                                                                         at="2026-11-03T12:00:00Z")])
    assert result.failed


def test_comment_command_after_last_commit_confirms_before_does_not(proposal_repo):
    assert not gate(proposal_repo, OWNER, comments=[comment("owner", "looks fine\n/pcat approve")]).failed
    assert gate(proposal_repo, OWNER, comments=[comment("owner", at="2026-11-03T09:00:00Z")]).failed
    assert gate(proposal_repo, OWNER, comments=[comment("owner", body="/pcat approved?")]).failed


def test_non_approver_is_ignored(proposal_repo):
    assert gate(proposal_repo, OWNER, reviews=[review("stranger")], comments=[comment("stranger")]).failed


def test_allow_author(proposal_repo):
    off = approvals.Config(approvers=("owner",), allow_author=False)
    on = approvals.Config(approvers=("owner",), allow_author=True)
    assert gate(proposal_repo, off, author="owner", comments=[comment("owner")]).failed
    result = gate(proposal_repo, on, author="owner", comments=[comment("owner")])
    assert not result.failed
    assert "allow_author is on" in approvals.format_result(result, on)


def test_codeowners(proposal_repo):
    repo, _, _ = proposal_repo
    (repo / ".github").mkdir()
    (repo / ".github" / "CODEOWNERS").write_text("* @someone\n*.py @carol @org/team\n/docs/ @dora\n")
    config = approvals.Config(codeowners=True)
    result = gate(proposal_repo, config)
    assert result.waiting[0]["may_confirm"] == ["carol"]
    assert not gate(proposal_repo, config, reviews=[review("carol")]).failed
    assert gate(proposal_repo, config, reviews=[review("dora")]).failed


def test_codeowners_rules():
    m = approvals._codeowners_matches
    assert m("*", "a/b.py") and m("*.py", "a/b.py") and not m("*.md", "a/b.py")
    assert m("/src/", "src/x/y.py") and not m("/src/", "lib/src.py")
    assert m("docs/", "a/docs/x.md") and m("/a/b.py", "a/b.py") and m("src/*", "src/x.py")


def test_config_loading(tmp_path):
    path = tmp_path / "approvers.yaml"
    path.write_text("approvers: ['@Alice', bob]\nallow_author: true\n")
    assert approvals.load_config(path) == approvals.Config(("alice", "bob"), False, True)
    for bad, msg in [("approvers: alice\n", "list"), ("approvers: [a]\nextra: 1\n", "unknown keys"),
                     ("codeowners: false\n", "list approvers"), ("approvers: [a]\nallow_author: yes-ish\n", "true or false")]:
        path.write_text(bad)
        with pytest.raises(approvals.PcatError, match=msg):
            approvals.load_config(path)


def test_cli_approvals_check(proposal_repo, monkeypatch):
    repo, base, head = proposal_repo
    (repo / ".pcat").mkdir()
    (repo / ".pcat" / "approvers.yaml").write_text("approvers: [owner]\n")
    fake = FakeClient(head, base)
    monkeypatch.setattr(approvals, "GitHubClient", lambda token, api: fake)
    args = ["approvals", "check", "--repo", "o/r", "--pr", "7", "--catalog", str(REPO_ROOT)]
    out = CliRunner().invoke(app, args)
    assert out.exit_code == 1 and "WAITING" in out.output and "@owner" in out.output, out.output
    fake.data["/repos/o/r/issues/7/comments"] = [comment("owner")]
    out = CliRunner().invoke(app, args)
    assert out.exit_code == 0 and "CONFIRMED" in out.output, out.output


def test_changed_since_unknown_commit_is_an_error(repo, narrowed):
    commit_file(repo, narrowed, "x")
    out = lint(str(repo / "client.py"), "--changed-since", "0" * 40)
    assert out.exit_code == 1 and "no such commit" in out.output


# Part C: PC111 marker removal ------------------------------------------------


@pytest.fixture(scope="module")
def clean() -> str:
    return CatalogService(REPO_ROOT).get_pattern(HTTP, {"f0": "fetch"})["code"]


def test_pc111_marker_removed_but_still_derived(repo, clean):
    base = commit_file(repo, clean, "marked pattern code")
    commit_file(repo, clean.replace(f"# pcat: {HTTP}@v1\n", "").replace(*NARROW), "drop the marker, narrow")
    data = lint_json(str(repo / "client.py"), "--changed-since", base)
    [finding] = data["findings"]
    assert finding["provenance"] == "marker-removed" and finding["pattern"] == f"{HTTP}@v1"
    codes = {d["code"]: d for d in finding["deviations"]}
    assert codes["PC111"]["severity"] == "high" and "# pcat: http.get_with_retry.requests@v1" in codes["PC111"]["message"]
    assert "PC100" in codes and data["failed"]
    assert data["summary"]["failing"] == 1  # only PC111 fails; the other deviations are advisory
    assert lint(str(repo / "client.py")).exit_code == 0  # without a base ref: only inferred, advisory


def test_pc111_can_be_approved(repo, clean):
    base = commit_file(repo, clean, "marked")
    unmarked = clean.replace(f"# pcat: {HTTP}@v1\n", "")
    approval = f"# pcat-allow: PC111 #{hash_of(unmarked)} -- this helper now follows our own client, not the pattern"
    commit_file(repo, unmarked.replace("def fetch(", approval + "\ndef fetch("), "approve")
    data = lint_json(str(repo / "client.py"), "--changed-since", base)
    dev = next(d for d in data["findings"][0]["deviations"] if d["code"] == "PC111")
    assert dev["approval_state"] == "proposed" and data["failed"]  # a proposal until confirmed


def test_no_pc111_when_the_function_was_deleted_or_rewritten(repo, clean):
    base = commit_file(repo, clean, "marked")
    commit_file(repo, clean.split(f"# pcat: {HTTP}@v1\n")[0] + "\n\ndef other():\n    return 1\n", "delete it")
    assert lint_json(str(repo / "client.py"), "--changed-since", base)["findings"] == []
    commit_file(repo, "def fetch(url):\n    return url.upper()\n", "rewrite: no longer derived")
    assert lint_json(str(repo / "client.py"), "--changed-since", base)["findings"] == []
