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


def test_parse_stream_tool_order_and_leaks(tmp_path):
    import json as _json

    lines = [
        _json.dumps({"type": "system"}),
        _json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Grep", "input": {"pattern": "def x"}},
            {"type": "text", "text": "hm"}]}}),
        _json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "mcp__pcat__search_patterns", "input": {"request": "x"}},
            {"type": "tool_use", "name": "mcp__pcat__get_pattern", "input": {"id": "a.b"}},
            {"type": "tool_use", "name": "Read", "input": {"file_path": "/home/user/pcat/.bench/apps/x.py"}}]}}),
        "not json",
        _json.dumps({"type": "result", "result": "done", "total_cost_usd": 0.1, "num_turns": 3, "duration_ms": 9}),
    ]
    s = v5.parse_stream(lines)
    assert s["finished"] and not s["is_error"] and s["cost_usd"] == 0.1 and len(s["tool_calls"]) == 4
    o = v5.tool_order(s["tool_calls"])
    assert o["searched"] and o["read_repo"] and o["read_before_search"] and o["fetched"] == ["a.b"]
    assert v5.leaks(s["tool_calls"], tmp_path, (".bench/apps",)) == [
        'Read: {"file_path": "/home/user/pcat/.bench/apps/x.py"}']
    assert v5.parse_stream([])["finished"] is False


def test_run_command_restricts_the_shell():
    cmd = v5.run_command("add x", "m", None)
    assert cmd[:3] == ["claude", "-p", "add x"] and "--mcp-config" not in cmd
    allowed = cmd[cmd.index("--allowedTools") + 1:cmd.index("--disallowedTools")]
    assert "Bash" not in allowed and "Edit" in allowed and any(a.startswith("Bash(git diff") for a in allowed)
    assert "WebFetch" in cmd and "--setting-sources" in cmd
    with_mcp = v5.run_command("add x", "m", tmp := __import__("pathlib").Path("/x/mcp.json"))
    assert with_mcp[3:5] == ["--mcp-config", str(tmp)] and "mcp__pcat__search_patterns" in with_mcp


def test_find_new_function_only_considers_changed_code(tmp_path):
    app = make_app(tmp_path)
    dest = tmp_path / "run"
    v5.prepare_workdir(app, dest, TASK, "baseline")
    ref = v5.reference_source(SOURCE, ("helper", "target"))
    path = dest / "pkg" / "mod.py"
    assert v5.find_new_function(dest, TASK, [], ref) is None  # nothing written yet
    path.write_text(path.read_text() + "\n\ndef renamed(y):\n    return helper(y)\n")
    _, files = v5.final_diff(dest)
    found = v5.find_new_function(dest, TASK, files, ref)
    assert (found["function"], found["how"]) == ("renamed", "most similar")
    path.write_text(path.read_text() + "\n\n@decorator\n@other(1)\ndef target(y):\n    return helper(y)\n")
    _, files = v5.final_diff(dest)
    found = v5.find_new_function(dest, TASK, files, ref)
    assert (found["function"], found["how"]) == ("target", "same name")
    assert v5.similarity_to_reference(found["node"], ref, "target") == 1.0


def test_summarize_runs():
    def rec(kind, status="ok", fetched=(), nf=None, high=0, failed=False, cost=0.1, pattern="p.q"):
        return {"kind": kind, "status": status, "pattern": pattern if kind == "pattern" else None,
                "tool_order": {"searched": bool(fetched), "read_before_search": True, "fetched": list(fetched)},
                "score": {"new_function": nf, "lint": {"failed": failed, "deviations": {"high": high, "medium": 0, "low": 1}}},
                "summary": {"cost_usd": cost}, "wall_seconds": 10, "files_changed": ["a.py"], "leaks": []}

    covered = {"status": "covered", "matches_pattern": "p.q", "marker": "p.q@v1", "similarity_to_original": 0.9,
               "inferred": {"pattern": "p.q", "derived": True}}
    other = {"status": "none", "matches_pattern": None, "marker": None, "similarity_to_original": 0.5,
             "inferred": {"pattern": "z.z", "derived": False}}
    s = v5.summarize_runs([
        rec("pattern", fetched=["p.q@v1"], nf=covered),
        rec("pattern", nf=other, high=1, failed=True),
        rec("negative", fetched=["p.q"], nf={**other, "marker": "p.q@v1"}, pattern=None),
        rec("pattern", status="timeout"),
    ])
    assert (s["runs"], s["ok"], s["timeouts"], s["pattern_runs"]) == (4, 3, 1, 2)
    assert (s["fetched_right_rate"], s["matches_rate"], s["derives_rate"]) == (0.5, 0.5, 0.5)
    assert s["median_similarity_pattern_tasks"] == 0.7 and s["lint_fail_rate"] == 0.333
    assert (s["negatives_fetched_a_pattern"], s["negatives_used_a_pattern"], s["negatives_forced_a_pattern"]) == (1, 1, 1)
    assert s["deviations"]["high"] == 1 and s["total_cost_usd"] == 0.3
