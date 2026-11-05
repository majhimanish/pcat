"""Variance experiment logic (no live generation)."""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import pytest

from pcatlab_tests.conftest import FIXTURES, REPO_ROOT
from pcatlab import variance
from pcat.errors import PcatError

FIXTURE_RUN = FIXTURES / "run"


# Extraction and validity --------------------------------------------------- #
def test_extract_fenced_block():
    text = "Here you go:\n```python\ndef f():\n    return 1\n```\nThanks"
    assert variance.extract_code(text) == "def f():\n    return 1\n"


def test_extract_without_fence_uses_whole_response():
    assert variance.extract_code("  def f():\n    return 1  \n") == "def f():\n    return 1\n"


def test_extract_first_python_block_of_several():
    text = (
        "```bash\npip install pyjwt\n```\n"
        "```py\ndef first():\n    pass\n```\n"
        "```python\ndef second():\n    pass\n```"
    )
    assert variance.extract_code(text) == "def first():\n    pass\n"
    assert variance.extract_code("```\ndef plain():\n    pass\n```") == "def plain():\n    pass\n"


@pytest.mark.parametrize(
    "code,reason",
    [
        ("def f(:\n", "syntax_error"),
        ("class A:\n    pass\n\ndef f():\n    pass\n", "contains_class"),
        ("def f():\n    class Inner:\n        pass\n", "contains_class"),
        ("x = 1\n", "no_function"),
        ("def f():\n    return 1\n", None),
    ],
)
def test_check_code(code, reason):
    result = variance.check_code(code)
    assert (result is None) if reason is None else result.startswith(reason)


# Metrics --------------------------------------------------------------------- #
def test_metrics_all_identical():
    assert variance.distribution_metrics(["a"] * 20) == {
        "distinct": 1, "top_share": 1.0, "effective": 1.0,
    }


def test_metrics_all_distinct():
    m = variance.distribution_metrics([str(i) for i in range(20)])
    assert m == {"distinct": 20, "top_share": 0.05, "effective": 20.0}


def test_metrics_known_mixed_distribution():
    m = variance.distribution_metrics(["a", "a", "b", "c"])
    expected = math.exp(-(0.5 * math.log(0.5) + 2 * 0.25 * math.log(0.25)))
    assert m == {"distinct": 3, "top_share": 0.5, "effective": round(expected, 2)}
    assert m["effective"] == 2.83
    assert variance.distribution_metrics([]) == {"distinct": 0, "top_share": 0.0, "effective": 0.0}


def test_import_roots_group_import_and_from_import():
    import ast

    a = variance.import_roots(ast.parse("import jwt\n"))
    b = variance.import_roots(ast.parse("from jwt import encode\n"))
    c = variance.import_roots(ast.parse("from jose import jwt\nimport os.path\nfrom . import x\n"))
    assert a == b == ("jwt",)
    assert c == ("jose", "os")
    assert variance.third_party(("datetime", "jose", "os", "passlib")) == ("jose", "passlib")


# Snippet normalization ------------------------------------------------------- #
def test_module_global_names_do_not_matter_and_main_guard_dropped():
    one = "from passlib.context import CryptContext\nctx = CryptContext(schemes=['bcrypt'])\n\ndef h(p):\n    return ctx.hash(p)\n"
    two = one.replace("ctx", "pwd_context") + "\nif __name__ == '__main__':\n    print(h('x'))\n"
    a, b = variance.snippet_info(one), variance.snippet_info(two)
    assert a.exact_fingerprint == b.exact_fingerprint
    assert a.module_statements == 1 and a.third_party == ("passlib",)
    assert "def f1():\n    global g0\n    g0 = CryptContext(schemes=['bcrypt'])" in a.canonical_text
    assert "return g0.hash(v0)" in a.canonical_text


def test_local_that_shadows_a_global_is_not_renamed_as_global():
    code = "app = make()\n\ndef f(app):\n    return app + 1\n\ndef g():\n    return app\n"
    text = variance.snippet_info(code).canonical_text
    assert "def f0(v0):\n    return v0 + 1" in text and "def f1():\n    return g0" in text


def test_snippet_info_descriptors():
    info = variance.snippet_info("import os\nimport jwt\n\ndef make(a, b=1, *c, d, **e):\n    return a\n\ndef other():\n    pass\n")
    assert (info.functions, info.entry_params, info.imports, info.third_party) == (
        2, 5, ("jwt", "os"), ("jwt",),
    )


# Prompts ------------------------------------------------------------------------ #
def test_build_prompts_for_each_condition():
    tasks = variance.load_tasks(REPO_ROOT / "experiments" / "variance" / "tasks.yaml")
    assert len(tasks["tasks"]) == 8
    suffix = tasks["suffix"].strip()
    a, va = variance.build_prompt(tasks, "jwt_create", "A", 7)
    assert va == "prompt" and a.endswith(suffix) and a.startswith(tasks["tasks"]["jwt_create"]["prompt"].strip())
    variants = [variance.build_prompt(tasks, "jwt_create", "B", i)[1] for i in range(20)]
    assert variants[:6] == ["paraphrase-1", "paraphrase-2", "paraphrase-3", "paraphrase-4", "paraphrase-5", "paraphrase-1"]
    assert all(variants.count(f"paraphrase-{k}") == 4 for k in range(1, 6))
    c, vc = variance.build_prompt(tasks, "jwt_create", "C", 2, reference="def ref():\n    pass\n")
    assert vc == "paraphrase-3+reference"
    assert variance.REFERENCE_INSTRUCTION in c and "```python\ndef ref():\n    pass\n```" in c and c.endswith(suffix)
    with pytest.raises(PcatError):
        variance.build_prompt(tasks, "jwt_create", "C", 0)


# Reference selection ------------------------------------------------------------ #
def row(sample, shape, exact):
    return {"sample": sample, "shape_fingerprint": shape, "exact_fingerprint": exact}


def test_reference_selection_is_deterministic():
    rows = [
        row(1, "S2", "e1"),
        row(2, "S1", "x1"), row(3, "S1", "x2"), row(4, "S1", "x2"), row(5, "S1", "x1"),
        row(6, "S1", "x2"), row(7, "S2", "e2"), row(8, "S2", "e2"),
        {"sample": 9, "invalid_reason": "contains_class"},
    ]
    # S1 is most common (5); in it x2 (3 samples) beats x1 (2); lowest sample in x2 is 3
    assert variance.select_reference(rows) == 3
    assert variance.select_reference(list(reversed(rows))) == 3


def test_reference_selection_tie_breaks_by_lowest_sample():
    rows = [row(4, "S1", "a"), row(2, "S2", "b"), row(3, "S2", "c"), row(1, "S1", "d")]
    # both shapes have 2; S1 contains sample 1; inside S1 both exact groups have 1 -> sample 1
    assert variance.select_reference(rows) == 1
    with pytest.raises(PcatError):
        variance.select_reference([{"sample": 1, "invalid_reason": "x"}])


# Backends ------------------------------------------------------------------------ #
def test_backend_selection_order():
    present = lambda name: "/usr/bin/claude"  # noqa: E731
    absent = lambda name: None  # noqa: E731
    assert variance.select_backend({"ANTHROPIC_API_KEY": "k"}, present) == "api"
    assert variance.select_backend({"ANTHROPIC_API_KEY": "k"}, absent) == "api"
    assert variance.select_backend({}, present) == "cli"
    assert variance.select_backend({"ANTHROPIC_API_KEY": ""}, present) == "cli"
    assert variance.select_backend({}, absent) == "subagent"


def test_cli_generator_isolation(monkeypatch, tmp_path):
    calls = {}

    class Done:
        returncode = 0
        stdout = json.dumps({
            "result": "```python\ndef f():\n    pass\n```", "is_error": False, "num_turns": 1,
            "modelUsage": {"claude-haiku-5-5": {"outputTokens": 3}, "claude-sonnet-5-5": {"outputTokens": 40}},
        })
        stderr = ""

    def fake_run(cmd, cwd, env, **kwargs):
        calls.update(cmd=cmd, cwd=cwd, env=env)
        return Done()

    monkeypatch.setenv("CLAUDE_ADDITIONAL_DIRECTORIES", "/somewhere")
    monkeypatch.setattr(variance.subprocess, "run", fake_run)
    gen = variance.CliGenerator("claude-sonnet-5-5", tmp_path / "w").generate("PROMPT")
    assert gen.model == "claude-sonnet-5-5" and gen.extra["num_turns"] == 1
    assert calls["cmd"][:3] == ["claude", "-p", "PROMPT"]
    assert "--no-session-persistence" in calls["cmd"] and "--strict-mcp-config" in calls["cmd"]
    assert "Bash" in calls["cmd"] and "Read" in calls["cmd"]
    assert "CLAUDE_ADDITIONAL_DIRECTORIES" not in calls["env"]
    assert Path(calls["cwd"]) == tmp_path / "w"


def test_retries_then_success_and_permanent_failure():
    class Flaky:
        def __init__(self, failures):
            self.failures, self.calls = failures, 0

        def generate(self, prompt):
            self.calls += 1
            if self.calls <= self.failures:
                raise variance.GenerationError(f"boom {self.calls}")
            return variance.Generation("ok", "m", None)

    sleeps = []
    gen, attempts, error = variance.generate_with_retries(Flaky(2), "p", sleep=sleeps.append)
    assert gen.text == "ok" and attempts == 3 and error is None and sleeps == [5, 10]
    gen, attempts, error = variance.generate_with_retries(Flaky(9), "p", sleep=sleeps.append)
    assert gen is None and attempts == 4 and error == "boom 4"


# Analysis -------------------------------------------------------------------- #
def test_analysis_numbers_on_fixture_run():
    analysis = variance.analyze_run(FIXTURE_RUN, ["demo"])
    a = analysis["tasks"]["demo"]["A"]["summary"]
    # samples: original, renamed copy, literal-changed copy, jose variant, class
    assert (a["samples"], a["valid"], a["invalid"]) == (5, 4, {"contains_class": 1})
    assert (a["distinct_exact"], a["distinct_shapes"]) == (3, 2)
    assert a["top_shape_share"] == 0.75
    assert a["distinct_third_party_sets"] == 2 and a["third_party_sets"] == {"jose": 1, "jwt": 3}
    b = analysis["tasks"]["demo"]["B"]["summary"]
    assert b["invalid"] == {"generation_failed": 1, "syntax_error": 1}
    # renaming the module-level SECRET global does not change the fingerprint
    assert b["distinct_exact"] == 2 and b["with_module_statements"] == 2


def test_analysis_is_byte_identical_across_runs(tmp_path):
    copy = tmp_path / "run"
    shutil.copytree(FIXTURE_RUN, copy)
    one = variance.analysis_json_text(variance.analyze_run(FIXTURE_RUN, ["demo"]))
    two = variance.analysis_json_text(variance.analyze_run(copy, ["demo"]))
    assert one == two
    assert "timestamp" not in one and "2026-11-02" not in one


def test_reference_match_rate_and_table():
    rows = variance.analyze_run(FIXTURE_RUN, ["demo"])["tasks"]["demo"]["A"]["samples"]
    first = next(r for r in rows if r["sample"] == 1)
    refs = {"demo": {"shape_fingerprint": first["shape_fingerprint"], "exact_fingerprint": first["exact_fingerprint"]}}
    # Pretend condition A were condition C to exercise the metric.
    tmp = FIXTURE_RUN  # read-only use
    analysis = variance.analyze_run(tmp, ["demo"], refs)
    assert "reference_match_rate" not in analysis["tasks"]["demo"]["A"]["summary"]
    table = variance.headline_table(analysis)
    assert table.splitlines()[0].startswith("| Task | Cond.") and "| demo | A | 4/5 | 3 | 2 | 0.75 |" in table


def test_reference_match_rate_for_condition_c(tmp_path):
    run = tmp_path / "run"
    shutil.copytree(FIXTURE_RUN / "demo" / "A", run / "demo" / "C")
    rows = variance.analyze_run(run, ["demo"])["tasks"]["demo"]["C"]["samples"]
    first = next(r for r in rows if r["sample"] == 1)
    refs = {"demo": {"shape_fingerprint": first["shape_fingerprint"], "exact_fingerprint": first["exact_fingerprint"]}}
    s = variance.analyze_run(run, ["demo"], refs)["tasks"]["demo"]["C"]["summary"]
    assert s["reference_match_rate"] == 0.75 and s["reference_exact_match_rate"] == 0.5


def test_supplementary_classes_removed_metric():
    pyd = (
        "from fastapi import Depends\nfrom pydantic import BaseModel\n\n"
        "class {m}(BaseModel):\n    name: str\n\n"
        "def create(payload: {m}, repo=Depends(get_repo)):\n    return repo(payload.name)\n"
    )
    rows = [
        variance.analyze_sample({"sample": i, "status": "ok", "code": pyd.format(m=m)})
        for i, m in enumerate(["UserIn", "NewUser"], 1)
    ]
    assert all(r["invalid_reason"] == "contains_class" for r in rows)
    # class names are treated like globals, so the two samples get the same shape
    assert rows[0]["classes_removed"]["shape_fingerprint"] == rows[1]["classes_removed"]["shape_fingerprint"]
    summary = variance.summarize(rows)
    assert summary["valid"] == 0
    assert summary["supplementary_classes_removed"] == {
        "samples": 2, "with_classes": 2, "distinct_shapes": 1, "top_shape_share": 1.0, "effective_shapes": 1.0,
    }
    nested = variance.analyze_sample(
        {"sample": 3, "status": "ok", "code": "def f():\n    class A:\n        pass\n    return A\n"}
    )
    assert "classes_removed" not in nested


def test_similarity_metrics():
    base = "def f0(v0):\n    return v0 + 0\n"
    near = "def f0(v0):\n    return int(v0) + 0\n"
    far = "import os\n\ndef f0():\n    for v0 in os.listdir(''):\n        print(v0, v0, v0)\n"
    assert variance.similarity_metrics([base, base]) == {"median_similarity": 1.0, "near_shape_groups": 1}
    m = variance.similarity_metrics([base, near, far])
    assert m["near_shape_groups"] == 2  # base and near link, far stays alone
    assert 0 < m["median_similarity"] < 1
    assert variance.similarity_metrics([base]) == {"median_similarity": 1.0, "near_shape_groups": 1}
    assert variance.similarity_metrics([]) == {"median_similarity": 0.0, "near_shape_groups": 0}
