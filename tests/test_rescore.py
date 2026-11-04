"""v5.1 re-scoring and survey helpers."""

from __future__ import annotations

from pcat import rescore


def test_survey_files_skip_tests_docs_and_migrations(tmp_path):
    for rel in ("app/views.py", "app/tests/test_views.py", "app/test_x.py", "app/x_test.py", "conftest.py",
                "docs/conf.py", "app/migrations/0001_initial.py", "app/models.py", ".hidden/x.py", "README.md"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("def f():\n    return 1\n\n\nclass A:\n    def m(self):\n        return 2\n")
    files = rescore.survey_files(tmp_path)
    assert files == ["app/models.py", "app/views.py"]
    assert rescore.count_functions(tmp_path, files) == 4  # methods count


def finding(provenance, *devs, function="f"):
    return {"path": "a.py", "function": function, "line": 1, "pattern": "p.q@v1", "provenance": provenance,
            "deviations": [{"code": c, "severity": s, "message": m, "approved": False} for c, s, m in devs]}


def run(app, sample, failed, *findings, condition="pcat"):
    counts = {s: sum(d["severity"] == s for f in findings for d in f["deviations"]) for s in rescore.SEVERITIES}
    return {"app": app, "task": "t", "condition": condition, "sample": sample,
            "lint": {"failed": failed, "deviations": counts, "findings": list(findings)}}


def test_compare_reports_flips_with_reasons():
    old = [run("a", 1, True, finding("marked", ("PC100", "high", "no longer calls K"), ("PC108", "low", "adds K"))),
           run("a", 2, False, finding("inferred", ("PC105", "medium", "x"))),
           run("a", 3, False, condition="baseline")]
    new = [run("a", 1, False, finding("marked", ("PC110", "low", "struct"))),
           run("a", 2, False, finding("inferred", ("PC105", "medium", "x"))),
           run("a", 3, False, condition="baseline")]
    result = rescore.compare_e2e(old, new)
    [flip] = result["flips"]
    assert (flip["sample"], flip["old_failed"], flip["new_failed"]) == (1, True, False)
    assert flip["old_failing"] == ["f: PC100 no longer calls K"] and flip["new_failing"] == []
    [changed] = result["changed_runs"]
    assert changed["removed"] == ["f: PC100 high: no longer calls K", "f: PC108 low: adds K"]
    assert result["tables"]["old"]["pcat"]["would_fail_ci"] == 1 and result["tables"]["new"]["pcat"]["would_fail_ci"] == 0
    assert result["tables"]["old"]["pcat"]["by_code"]["PC100"]["high"] == 1
    assert "a/t/pcat/1: fail -> pass" in rescore.e2e_markdown(result)


def test_medium_high_items_and_reproducible_sample():
    findings = [finding("inferred", ("PC105", "medium", "m"), ("PC108", "low", "l"), function=f"f{i}")
                for i in range(40)]
    items = rescore.medium_high(findings)
    assert len(items) == 40 and {i["code"] for i in items} == {"PC105"}
    a, b = rescore.sample(items, 30, "ctfd"), rescore.sample(items, 30, "ctfd")
    assert a == b and len(a) == 30 and rescore.sample(items[:5], 30, "x") == items[:5]
    summary = rescore.survey_summary({"findings": findings})
    assert summary["inferred_derived"] == 40 and summary["by_severity"] == {"high": 0, "medium": 40, "low": 40}
