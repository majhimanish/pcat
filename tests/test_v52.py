"""v5.2 Part A: planted neighbours, manifests and the guard checks behind them (no claude -p)."""

from __future__ import annotations

import ast
import re
import subprocess

import pytest

from conftest import REPO_ROOT
from pcat import catalog as cat
from pcat import v5, v52
from pcat.errors import PcatError

V52 = REPO_ROOT / "experiments" / "v5.2"
TASKS = v52.load_tasks(V52 / "tasks.yaml")
HINTS = re.compile(r"old|legacy|insecure|unsafe|deprecated|planted|vulnerab|todo|fixme|hack|weak|bad",
                   re.IGNORECASE)


def pattern_of(task):
    return cat.get_one(REPO_ROOT / "experiments" / "v5" / "catalogs" / task.app, task.pattern)


def test_six_tasks_per_app_on_guarded_patterns():
    assert len(TASKS) == 18
    for app in ("ctfd", "healthchecks", "lnbits"):
        assert sum(t.app == app for t in TASKS) == 6
    for t in TASKS:
        meta = pattern_of(t).meta
        assert meta.guards, t.id
        keys = {v52.guard_key(g.kind, " | ".join(g.names) if g.match == "any" else (g.target or n))
                for g in meta.guards if (g.function or meta.entry_point) == t.neighbour.pattern_function
                for n in (g.names or [g.target])}
        assert set(t.neighbour.violates) <= keys, t.id  # only guards that exist, unchanged


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_neighbour_is_one_plausible_function(task):
    code = v52.neighbour_code(REPO_ROOT, task)
    tree = ast.parse(code)
    texts = [task.neighbour.function, *re.findall(r"#.*|\"\"\"[\s\S]*?\"\"\"", code)]
    texts += [n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]
    assert not [t for t in texts if HINTS.search(t)], task.id


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_neighbour_violates_its_guards_and_the_original_passes(task):
    """On the committed skeleton of the target file (imports, constants, stubs)."""
    context = (V52 / "context" / task.app / f"{task.id}.py").read_text()
    reference = (V52 / "references" / task.app / f"{task.id}.py").read_text()
    code = v52.neighbour_code(REPO_ROOT, task)
    pattern = pattern_of(task)
    module = v52.module_from_rel(task.file)
    planted = v52.plant(context, code, task.neighbour.anchor)
    res = v52.guard_results(planted, task.neighbour.function, pattern, task.neighbour.pattern_function, module)
    assert set(task.neighbour.violates) <= v52.violated(res) and not v52.skipped(res)
    restored = context + "\n\n" + reference
    checked = 0
    for fn, pfn in task.targets:
        r = v52.guard_results(restored, fn, pattern, pfn, module)
        assert not v52.violated(r) and not v52.skipped(r), (task.id, fn)
        checked += len(r)
    assert checked >= 1


SOURCE = "import os\n\n\ndef a():\n    return 1\n\n\n# about b\n@dec\ndef b():\n    return 2\n"
NEW = "def n():\n    return os.sep\n"


def test_plant_after_before_and_append():
    after = v52.plant(SOURCE, NEW, ("after", "a"))
    assert after.index("def a") < after.index("def n") < after.index("# about b")
    before = v52.plant(SOURCE, NEW, ("before", "b"))
    assert before.index("def n") < before.index("# about b") and "\n\n\ndef n" in before
    appended = v52.plant(SOURCE, NEW, ("append", None))
    assert appended.endswith("def n():\n    return os.sep\n")
    for text in (after, before, appended):
        ast.parse(text)
        assert "\n\n\n\n" not in text
    with pytest.raises(PcatError, match="already exists"):
        v52.plant(SOURCE, "def a():\n    pass\n", ("append", None))
    with pytest.raises(PcatError, match="not found"):
        v52.plant(SOURCE, NEW, ("after", "zzz"))


def test_skeleton_keeps_imports_constants_and_called_functions():
    src = ("import os\nfrom a import b as c\nLIMIT = 3\nthing = make()\n\n\nclass K:\n    x = 1\n\n\n"
           "def helper(v):\n    return v\n\n\ndef other():\n    return 2\n")
    sk = v52.context_for(src, ["def f(x):\n    return helper(x)\n"])
    assert "import os" in sk and "from a import b as c" in sk and "LIMIT = 3" in sk
    assert "thing = None" in sk and "class K:\n    ..." in sk
    assert "def helper(v):\n    return v" in sk and "def other(*args, **kwargs):\n    ..." in sk


def test_module_from_rel():
    assert v52.module_from_rel("CTFd/utils/decorators/__init__.py") == "CTFd.utils.decorators"
    assert v52.module_from_rel("lnbits/helpers.py") == "lnbits.helpers"


def test_prepare_workdir_plants_before_the_baseline_commit(tmp_path):
    app = tmp_path / "app"
    (app / "pkg").mkdir(parents=True)
    (app / "pkg" / "mod.py").write_text(SOURCE)
    task = v52.Task("app", "t", "pkg/mod.py", ("b",), "x.y", "same", "need", (("b", "b"),),
                    v52.Neighbour("n", ("after", "a"), "b", ("must_call:os.sep",), "flaw", "realism"))
    dest = tmp_path / "run"
    v52.prepare_workdir(app, dest, task, "baseline", NEW)
    text = (dest / "pkg" / "mod.py").read_text()
    assert "def n():" in text and "def b():" not in text and "def a():" in text
    assert v5.final_diff(dest) == ("", [])
    log = subprocess.run(["git", "log", "--oneline"], cwd=dest, capture_output=True, text=True).stdout
    assert log.count("\n") == 1


def test_load_tasks_rejects_bad_manifests(tmp_path):
    base = ("apps:\n  a:\n    t:\n      file: f.py\n      remove: [x]\n      pattern: p.q\n      relation: same\n"
            "      need: n\n      targets: {x: x}\n      neighbour:\n        function: y\n"
            "        pattern_function: x\n        flaw: f\n        realism: r\n")
    path = tmp_path / "tasks.yaml"
    path.write_text(base + "        anchor: {after: x}\n        violates: []\n")
    with pytest.raises(PcatError, match="at least one guard"):
        v52.load_tasks(path)
    path.write_text(base + "        anchor: {middle: x}\n        violates: [{kind: must_call, item: a.b}]\n")
    with pytest.raises(PcatError, match="anchor"):
        v52.load_tasks(path)
    path.write_text(base.replace("targets: {x: x}", "targets: {z: x}")
                    + "        anchor: {after: x}\n        violates: [{kind: must_call, item: a.b}]\n")
    with pytest.raises(PcatError, match="targets"):
        v52.load_tasks(path)


def test_request_filter_rejects_security_words_and_the_planted_name():
    task = TASKS[0]
    assert v52.request_problems("Add a decorator that redirects anonymous users", task) == []
    assert v52.request_problems("Add a forgot-password token helper", task) == []
    assert v52.request_problems("Check the next URL is safe", task) == ["mentions 'safe'"]
    assert v52.request_problems(f"Like {task.neighbour.function}", task) == ["names the planted function"]
    assert v52.request_problems(None, task) == ["empty"]


def test_committed_requests_follow_the_rule():
    import json

    items = json.loads((V52 / "requests.json").read_text())["items"]
    by_id = {t.id: t for t in TASKS}
    assert sorted(i["id"] for i in items) == sorted(by_id)
    for item in items:
        assert v52.request_problems(item["request"], by_id[item["id"]]) == []
        assert item["need"] == by_id[item["id"]].need
