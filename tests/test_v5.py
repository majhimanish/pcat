"""v5 simulation helpers: tasks, function removal, working copies, requests (no claude -p)."""

from __future__ import annotations

import subprocess

import pytest

from conftest import REPO_ROOT
from pcat import v5
from pcat.errors import PcatError

SOURCE = '''\
import os


# A comment that belongs to the helper
def helper(x):
    return x + 1


@decorator
@other(1)
def target(y):
    """Doc."""
    return helper(y)


def keep():
    return os.sep
'''


def test_remove_functions_keeps_the_rest_valid():
    new, refs = v5.remove_functions(SOURCE, ("helper", "target"))
    assert "def helper" not in new and "def target" not in new and "@decorator" not in new
    assert "A comment that belongs" not in new  # the comment block above goes too
    assert "def keep():" in new and new.startswith("import os\n")
    assert refs["target"].startswith("@decorator\n@other(1)\ndef target(y):")
    assert refs["helper"].startswith("# A comment that belongs to the helper\ndef helper")
    compile(new, "x.py", "exec")


def test_reference_source_in_source_order():
    ref = v5.reference_source(SOURCE, ("target", "helper"))
    assert ref.index("def helper") < ref.index("def target") and ref.endswith("\n")


def test_missing_or_duplicate_functions_are_errors():
    with pytest.raises(PcatError, match="no top-level function"):
        v5.remove_functions(SOURCE, ("nope",))
    with pytest.raises(PcatError, match="more than once"):
        v5.remove_functions(SOURCE + "\n\ndef keep():\n    return 2\n", ("keep",))


def test_load_tasks_from_the_real_file():
    tasks = v5.load_tasks(REPO_ROOT / "experiments" / "v5" / "tasks.yaml")
    assert len(tasks) == 24
    for app in ("ctfd", "healthchecks", "lnbits"):
        mine = [t for t in tasks if t.app == app]
        assert sum(t.kind == "pattern" for t in mine) == 6 and sum(t.kind == "negative" for t in mine) == 2
    assert all(t.need and "  " not in t.need for t in tasks)


def test_load_tasks_rejects_inconsistent_kinds(tmp_path):
    path = tmp_path / "tasks.yaml"
    path.write_text("apps:\n  a:\n    t:\n      kind: negative\n      file: x.py\n      remove: [f]\n"
                    "      pattern: some.pattern\n      need: n\n")
    with pytest.raises(PcatError, match="pattern tasks need a pattern"):
        v5.load_tasks(path)


def make_app(tmp_path):
    app = tmp_path / "app"
    (app / "pkg").mkdir(parents=True)
    (app / "pkg" / "mod.py").write_text(SOURCE)
    (app / ".git").mkdir()  # ignored when copying
    (app / ".git" / "HEAD").write_text("junk")
    return app


TASK = v5.Task("app", "t1", "pattern", "pkg/mod.py", ("helper", "target"), "x.y", "sibling", "need")


@pytest.mark.parametrize("condition", ["baseline", "pcat"])
def test_prepare_workdir_and_final_diff(tmp_path, condition):
    app = make_app(tmp_path)
    dest = tmp_path / "run"
    info = v5.prepare_workdir(app, dest, TASK, condition)
    assert len(info["baseline"]) == 40
    assert "def target" not in (dest / "pkg" / "mod.py").read_text()
    assert ((dest / "CLAUDE.md").exists()) is (condition == "pcat")
    if condition == "pcat":
        assert (dest / "CLAUDE.md").read_text() == v5.REPO_NOTE + "\n"
    assert v5.final_diff(dest) == ("", [])  # the setup is in the baseline commit
    (dest / "pkg" / "mod.py").write_text((dest / "pkg" / "mod.py").read_text() + "\ndef target(y):\n    return y\n")
    (dest / "pkg" / "new.py").write_text("x = 1\n")
    diff, files = v5.final_diff(dest)
    assert "+def target(y):" in diff and files == ["pkg/mod.py", "pkg/new.py"]
    log = subprocess.run(["git", "log", "--oneline"], cwd=dest, capture_output=True, text=True).stdout
    assert log.count("\n") == 1


def test_pcat_note_appends_to_an_existing_claude_md(tmp_path):
    app = make_app(tmp_path)
    (app / "CLAUDE.md").write_text("# Project rules")
    dest = tmp_path / "run"
    v5.prepare_workdir(app, dest, TASK, "pcat")
    assert (dest / "CLAUDE.md").read_text() == "# Project rules\n" + v5.REPO_NOTE + "\n"


def test_request_jobs_and_prompt():
    jobs = v5.request_jobs([TASK], {"app": [{"need": "a  b", "expected": None}, {"need": "c", "expected": "p.q"}]})
    assert [j["id"] for j in jobs] == ["t1", "app_extra_01", "app_extra_02"]
    assert [j["kind"] for j in jobs] == ["pattern", "negative", "pattern"]
    assert jobs[1]["need"] == "a b" and "under 15 words" in jobs[0]["prompt"] and "need" in jobs[0]["prompt"]
    assert v5.word_count(" add a  helper ") == 3


def test_overlap_summary_and_below_threshold():
    items = [
        {"request": "a", "expected": "h.x", "ranked": [("h.x", 20.0), ("g.y", 12.0)]},
        {"request": "b", "expected": "g.y", "ranked": [("h.x", 15.0), ("g.y", 14.0)]},
        {"request": "c", "expected": "h.x", "ranked": [("h.x", 8.0)]},
        {"request": "d", "expected": None, "ranked": [("g.y", 3.0)]},
    ]
    o = v5.overlap_summary(items, {"h.x"}, 9.08)
    assert (o["both_above_threshold"], o["house_first"], o["generic_first"], o["first_is_expected"]) == (2, 2, 0, 1)
    b = v5.below_threshold(items, 9.08)
    assert b["positives"] == 3 and b["ranked_first_but_below_threshold"] == 1 and b["examples"][0]["request"] == "c"
