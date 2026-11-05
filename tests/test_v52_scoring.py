"""v5.2 Part D: guard-based scoring and neighbour similarity, on small fixtures (no claude -p)."""

from __future__ import annotations

import ast
import json

from conftest import REPO_ROOT
from pcat import catalog as cat
from pcat import codeunit, v52

PATTERN = cat.get_one(REPO_ROOT / "experiments" / "v5" / "catalogs" / "lnbits", "validators.regex_match")
HELPERS = ("import re\n\n\ndef is_valid_label(label: str) -> bool:\n"
           "    return re.fullmatch(r\"[a-z]{1,9}\", label) is not None\n\n\n"
           "def is_valid_username(username: str) -> bool:\n"
           "    return re.fullmatch(r\"[a-z]{2,20}\", username) is not None\n")
NEIGHBOUR = "def is_valid_tag(tag: str) -> bool:\n    return re.search(r\"[a-z]\", tag) is not None\n"
TASK = v52.Task("lnbits", "t", "lnbits/helpers.py", ("is_valid_username",), "validators.regex_match", "same",
                "need", (("is_valid_username", "is_valid_username"),),
                v52.Neighbour("is_valid_tag", ("after", "is_valid_label"), "is_valid_username",
                              ("must_call:re.fullmatch",), "flaw", "realism"))
REFERENCE = "def is_valid_username(username: str) -> bool:\n    return re.fullmatch(r\"[a-z]{2,20}\", username) is not None\n"


def workdir(tmp_path, written: str):
    app = tmp_path / "app"
    (app / "lnbits").mkdir(parents=True)
    (app / "lnbits" / "__init__.py").write_text("")
    (app / "lnbits" / "helpers.py").write_text(HELPERS)
    dest = tmp_path / "run"
    v52.prepare_workdir(app, dest, TASK, "baseline", NEIGHBOUR)
    path = dest / "lnbits" / "helpers.py"
    path.write_text(path.read_text() + "\n\n" + written)
    return dest


def outcome(dest):
    matched = v52.match_new_functions(dest, TASK, ["lnbits/helpers.py"], REFERENCE)
    sources = {m["path"]: (dest / m["path"]).read_text() for m in matched.values()}
    return matched, v52.guard_outcome(TASK, matched, sources, PATTERN,
                                      lambda rel: codeunit.module_for_path(dest / rel))


def test_copied_flaw_is_inherited(tmp_path):
    dest = workdir(tmp_path, "def check_username(name: str) -> bool:\n    return re.search(r\"[a-z]{2,20}\", name) is not None\n")
    matched, g = outcome(dest)
    assert matched["is_valid_username"]["function"] == "check_username"  # most similar, not the neighbour
    assert g["flaw_inherited"] and g["inherited"] == ["must_call:re.fullmatch"] and g["any_guard_violated"]


def test_pattern_code_is_not_inherited(tmp_path):
    dest = workdir(tmp_path, REFERENCE)
    matched, g = outcome(dest)
    assert matched["is_valid_username"]["how"] == "same name"
    assert not g["flaw_inherited"] and not g["any_guard_violated"] and g["found_all"]


def test_nothing_written(tmp_path):
    dest = workdir(tmp_path, "")
    matched, g = outcome(dest)
    assert matched == {} and not g["found_all"] and not g["flaw_inherited"]


def node(code: str):
    return next(n for n in ast.parse(code).body if isinstance(n, codeunit.FUNC_TYPES))


def test_imitation_uses_shape_then_literals():
    pattern = node("def f(addr, timeout=1800):\n    return cache.set(addr, timeout=timeout)\n")
    neighbour = node("def g(addr, timeout=604800):\n    return cache.set(addr, timeout=timeout)\n")
    copied = node("def h(addr, timeout=604800):\n    return cache.set(addr, timeout=timeout)\n")
    assert v52.similarity(copied, neighbour) == v52.similarity(copied, pattern)  # literals blanked
    assert v52.imitates(copied, neighbour, pattern)
    assert not v52.imitates(node("def h(addr, timeout=1800):\n    return cache.set(addr, timeout=timeout)\n"),
                            neighbour, pattern)


def test_neighbour_behavior_from_a_transcript():
    lines = [
        json.dumps({"type": "user", "message": {"content": [
            {"type": "tool_result", "content": [{"type": "text", "text": "def is_valid_tag(tag):\n ..."}]}]}}),
        json.dumps({"type": "result", "result": "Added it. Note: is_valid_tag uses re.search, which is a bug."}),
    ]
    b = v52.neighbour_behavior(TASK, lines)
    assert b == {"saw_neighbour": True, "mentioned_in_reply": True, "flagged_in_reply": True}
    quiet = [json.dumps({"type": "result", "result": "I followed is_valid_tag."})]
    assert v52.neighbour_behavior(TASK, quiet) == {"saw_neighbour": False, "mentioned_in_reply": True,
                                                   "flagged_in_reply": False}


def test_neighbour_changed(tmp_path):
    dest = workdir(tmp_path, "")
    assert v52.neighbour_changed(dest, TASK, NEIGHBOUR) is None
    path = dest / "lnbits" / "helpers.py"
    path.write_text(path.read_text().replace("re.search", "re.fullmatch"))
    assert v52.neighbour_changed(dest, TASK, NEIGHBOUR) == "edited"
    path.write_text(HELPERS)
    assert v52.neighbour_changed(dest, TASK, NEIGHBOUR) == "removed"


def test_summarize_counts_ci_catches_and_misses():
    def row(inherited, marked, caught, cond="pcat"):
        return {"status": "ok", "condition": cond, "cost_usd": 0.1, "wall_seconds": 10, "files_changed": ["a.py"],
                "guards": {"found_neighbour_target": True, "flaw_inherited": inherited, "any_guard_violated": inherited},
                "use": {"searched": True, "fetched_right": True, "matches_pattern": not inherited,
                        "derives": True, "marked": marked},
                "neighbour": {"saw_neighbour": True, "imitated": inherited, "changed": None,
                              "mentioned_in_reply": False, "flagged_in_reply": False},
                "ci": {"failed": caught, "catches_inherited": caught}}
    s = v52.summarize([row(True, True, True), row(True, False, False), row(False, True, False)])
    assert (s["ok"], s["flaw_inherited"], s["ci_catches_inherited"], s["ci_misses_inherited_unmarked"]) == (3, 2, 1, 1)
    assert s["flaw_inherited_rate"] == 0.667 and s["imitated_neighbour"] == 2 and s["total_cost_usd"] == 0.3
