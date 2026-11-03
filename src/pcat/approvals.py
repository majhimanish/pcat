"""Human confirmation of proposed approvals on GitHub pull requests (v4.1 Part B).

A *proposed* approval (`# pcat-allow: PCxxx #<hash> -- reason`, new since the
base ref) approves nothing until an approver confirms the pull request after
its latest commit, by an approving review on the head commit or a comment
containing `/pcat approve` posted after the head commit's time. Approvers come
from `.pcat/approvers.yaml`:

    approvers: [alice, bob]   # GitHub usernames
    codeowners: true          # also anyone CODEOWNERS lists for the file
    allow_author: false       # true = the PR author may confirm (solo mode; weaker)

The GitHub API is reached through a small client object so tests can pass a
fake one; nothing here prints or exits.
"""

from __future__ import annotations

import datetime as dt
import fnmatch
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from pcat import lint
from pcat.errors import PcatError

CONFIG_PATH = Path(".pcat") / "approvers.yaml"
APPROVE_COMMAND = re.compile(r"(?:^|\s)/pcat approve(?:\s|$)")
CODEOWNERS_LOCATIONS = (Path(".github") / "CODEOWNERS", Path("CODEOWNERS"), Path("docs") / "CODEOWNERS")


# --------------------------------------------------------------------------- #
# Configuration and CODEOWNERS
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Config:
    approvers: tuple[str, ...] = ()
    codeowners: bool = False
    allow_author: bool = False


def load_config(path: Path) -> Config:
    if not path.is_file():
        raise PcatError(f"no approver config at {path} (see `pcat approvals check --help`)")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise PcatError(f"{path}: expected a mapping")
    unknown = sorted(set(data) - {"approvers", "codeowners", "allow_author"})
    if unknown:
        raise PcatError(f"{path}: unknown keys: {', '.join(unknown)}")
    approvers = data.get("approvers") or []
    if not isinstance(approvers, list) or not all(isinstance(a, str) and a.strip() for a in approvers):
        raise PcatError(f"{path}: approvers must be a list of GitHub usernames")
    for key in ("codeowners", "allow_author"):
        if not isinstance(data.get(key, False), bool):
            raise PcatError(f"{path}: {key} must be true or false")
    if not approvers and not data.get("codeowners"):
        raise PcatError(f"{path}: list approvers or set codeowners: true")
    return Config(tuple(a.strip().lstrip("@").lower() for a in approvers),
                  bool(data.get("codeowners", False)), bool(data.get("allow_author", False)))


def _codeowners_matches(pattern: str, path: str) -> bool:
    if pattern in ("*", "/*"):
        return True
    anchored = pattern.startswith("/")
    pat = pattern.lstrip("/")
    if pat.endswith("/"):
        prefix = pat.rstrip("/")
        if anchored or "/" in prefix:
            return path == prefix or path.startswith(prefix + "/")
        return prefix in path.split("/")[:-1]
    if anchored or "/" in pat:  # relative to the repository root; a directory covers its contents
        return fnmatch.fnmatchcase(path, pat) or fnmatch.fnmatchcase(path, pat.rstrip("/") + "/*")
    return fnmatch.fnmatchcase(path.rsplit("/", 1)[-1], pat) or any(
        fnmatch.fnmatchcase(part, pat) for part in path.split("/")[:-1])


def codeowners_for(path: str, root: Path) -> set[str]:
    """Users (lower-case, no @) CODEOWNERS assigns to `path` (last matching rule wins).
    Teams (`@org/team`) and e-mail owners are not resolved."""
    for loc in CODEOWNERS_LOCATIONS:
        file = root / loc
        if file.is_file():
            owners: list[str] = []
            for raw in file.read_text(encoding="utf-8").splitlines():
                line = raw.split("#", 1)[0].strip()
                if not line:
                    continue
                pattern, *names = line.split()
                if _codeowners_matches(pattern, path):
                    owners = names
            return {o[1:].lower() for o in owners if o.startswith("@") and "/" not in o}
    return set()


def may_confirm(path: str, config: Config, root: Path, author: str | None) -> list[str]:
    users = set(config.approvers)
    if config.codeowners:
        users |= codeowners_for(lint.normalize_path(path), root)
    if author and not config.allow_author:
        users.discard(author.lower())
    return sorted(users)


# --------------------------------------------------------------------------- #
# GitHub
# --------------------------------------------------------------------------- #


class GitHubClient:
    """Minimal GitHub REST client (urllib). `get_all` follows page numbers."""

    def __init__(self, token: str | None, api: str = "https://api.github.com"):
        self.token = token
        self.api = api.rstrip("/")

    def get(self, path: str, params: dict | None = None):
        url = f"{self.api}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "pcat-approvals", **({"Authorization": f"Bearer {self.token}"} if self.token else {}),
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise PcatError(f"GitHub API {path}: HTTP {exc.code} {exc.reason}") from None
        except urllib.error.URLError as exc:
            raise PcatError(f"GitHub API {path}: {exc.reason}") from None

    def get_all(self, path: str) -> list:
        out, page = [], 1
        while True:
            batch = self.get(path, {"per_page": 100, "page": page})
            out.extend(batch)
            if len(batch) < 100:
                return out
            page += 1


def _time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass
class PullRequest:
    number: int
    author: str
    head_sha: str
    base_sha: str
    head_time: dt.datetime
    reviews: list[dict] = field(default_factory=list)
    comments: list[dict] = field(default_factory=list)


def fetch_pull_request(client, repo: str, number: int) -> PullRequest:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise PcatError(f"--repo must be OWNER/REPO, got {repo!r}")
    pr = client.get(f"/repos/{repo}/pulls/{number}")
    head = pr["head"]["sha"]
    commit = client.get(f"/repos/{repo}/commits/{head}")
    return PullRequest(
        number=number, author=pr["user"]["login"], head_sha=head, base_sha=pr["base"]["sha"],
        head_time=_time(commit["commit"]["committer"]["date"]),
        reviews=client.get_all(f"/repos/{repo}/pulls/{number}/reviews"),
        comments=client.get_all(f"/repos/{repo}/issues/{number}/comments"),
    )


@dataclass(frozen=True)
class Confirmation:
    user: str
    kind: str  # "review" | "comment"
    when: str


def confirmations(pr: PullRequest) -> list[Confirmation]:
    """Approving reviews of the head commit and `/pcat approve` comments after it.

    A user's latest decisive review on the head commit counts (APPROVED yes;
    CHANGES_REQUESTED or DISMISSED cancel an earlier approval)."""
    latest: dict[str, dict] = {}
    for review in sorted(pr.reviews, key=lambda r: r.get("submitted_at") or ""):
        if review.get("commit_id") != pr.head_sha or not review.get("user"):
            continue
        if review.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[review["user"]["login"].lower()] = review
    out = [Confirmation(user, "review", r.get("submitted_at") or "")
           for user, r in sorted(latest.items()) if r["state"] == "APPROVED"]
    for comment in pr.comments:
        body, created = comment.get("body") or "", comment.get("created_at")
        if comment.get("user") and created and APPROVE_COMMAND.search(body) and _time(created) > pr.head_time:
            out.append(Confirmation(comment["user"]["login"].lower(), "comment", created))
    return sorted(out, key=lambda c: (c.when, c.user, c.kind))


# --------------------------------------------------------------------------- #
# The gate
# --------------------------------------------------------------------------- #


@dataclass
class Result:
    pr: PullRequest
    base: str
    waiting: list[dict]  # proposals without a valid confirmation (with "may_confirm")
    confirmed: list[dict]  # proposals with one (with "confirmed_by")
    report: lint.Report  # the lint report with confirmed proposals applied
    confirmations: list[Confirmation]
    head_mismatch: str | None = None

    @property
    def failed(self) -> bool:
        return bool(self.waiting) or self.report.failed


def merge_base(base_sha: str, cwd: Path) -> str:
    proc = subprocess.run(["git", "-C", str(cwd), "merge-base", base_sha, "HEAD"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise PcatError(f"cannot find the merge base with {base_sha[:12]} (check out with fetch-depth: 0): "
                        f"{proc.stderr.strip()}")
    return proc.stdout.strip()


def local_head(cwd: Path) -> str | None:
    proc = subprocess.run(["git", "-C", str(cwd), "rev-parse", "HEAD"], capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def check(pr: PullRequest, paths: list[str], catalog_root: Path, repo_root: Path, config: Config,
          base: str | None = None, fail_on: str = "high") -> Result:
    """Lint the pull request's changes and decide which proposals are confirmed."""
    base = base or merge_base(pr.base_sha, repo_root)
    first = lint.lint_paths(paths, catalog_root, include_inferred=False, fail_on=fail_on, changed_since=base)
    confs = confirmations(pr)
    waiting, confirmed, keys = [], [], set()
    for proposal in first.proposals:
        allowed = may_confirm(proposal["path"], config, repo_root, pr.author)
        by = sorted({c.user for c in confs if c.user in allowed})
        item = {**proposal, "may_confirm": allowed}
        if by:
            confirmed.append({**item, "confirmed_by": by})
            keys.add((lint.normalize_path(proposal["path"]), proposal["function"], proposal["code"], proposal["hash"]))
        else:
            waiting.append(item)
    report = first if not keys else lint.lint_paths(
        paths, catalog_root, include_inferred=False, fail_on=fail_on, changed_since=base, confirmed_proposals=keys)
    head = local_head(repo_root)
    mismatch = None if head in (None, pr.head_sha) else (
        f"the checked-out commit {head[:12]} is not the pull request head {pr.head_sha[:12]}")
    return Result(pr, base, waiting, confirmed, report, confs, mismatch)


def format_result(result: Result, config: Config) -> str:
    pr = result.pr
    out = [f"pcat approvals: pull request #{pr.number} (head {pr.head_sha[:12]}, author @{pr.author}, "
           f"base {result.base[:12]})"]
    if result.head_mismatch:
        out.append(f"warning: {result.head_mismatch}")
    if config.allow_author:
        out.append("note: allow_author is on: the author may confirm their own proposals "
                   "(solo-developer mode; this weakens the guarantee)")
    when = pr.head_time.strftime("%Y-%m-%d %H:%M:%SZ")
    for item in result.waiting:
        who = ", ".join(f"@{u}" for u in item["may_confirm"]) or "nobody (check .pcat/approvers.yaml)"
        out.append(f"WAITING {item['path']}:{item['line']}: {item['code']} #{item['hash']} in "
                   f"`{item['function']}` -- {item['reason']}")
        out.append(f"  may confirm: {who}, by an approving review of commit {pr.head_sha[:12]} or a "
                   f"comment containing '/pcat approve' posted after {when}")
    for item in result.confirmed:
        out.append(f"CONFIRMED {item['path']}:{item['line']}: {item['code']} #{item['hash']} in "
                   f"`{item['function']}` by {', '.join('@' + u for u in item['confirmed_by'])}")
    failing = [(f, d) for f in result.report.findings for d in f.failing(result.report.fail_on)]
    for f, d in failing:
        state = " (approval proposed, not confirmed)" if d.get("approval_state") == "proposed" else ""
        out.append(f"FAILING {f.path}:{d['line']}: {d['code']} {d['severity']} #{d.get('hash')}: "
                   f"{d['message']}{state}")
    for m in result.report.messages:
        if m.level == "error":
            out.append(f"ERROR {m.path}:{m.line}: {m.text}")
    if not result.waiting and not result.confirmed:
        out.append("no proposed approvals in this pull request")
    out.append(f"{len(result.waiting)} waiting, {len(result.confirmed)} confirmed; "
               f"{len(failing)} failing deviation(s): " + ("FAIL" if result.failed else "OK"))
    return "\n".join(out) + "\n"
