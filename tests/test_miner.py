"""Miner: discovery, filters, function clusters, coverage, report, cache."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from conftest import REPO_ROOT
from pcat import canonical, miner, shape
from pcat.cli import app
from pcat.miner import MineSettings

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "miner"
TOTAL_SHAPE_MEMBERS = {"total_price", "cached_total", "total_cost", "legacy_total", "sum_large"}


def run(inputs=None, settings=None, **kwargs):
    kwargs.setdefault("cache_dir", None)
    kwargs.setdefault("catalog_root", REPO_ROOT)
    inputs = inputs or [str(FIXTURES)]
    return miner.mine(inputs, settings or MineSettings(min_occurrences=2), **kwargs)


def clusters_by_member(report):
    return {
        frozenset(m["qualname"] for m in c["members"]): c for c in report["function_clusters"]
    }


@pytest.fixture(scope="module")
def report():
    return run().report


@pytest.fixture
def tree(tmp_path):
    dst = tmp_path / "src"
    shutil.copytree(FIXTURES, dst)
    return dst


# Part A: shapes and clusters ------------------------------------------------ #
def test_same_shape_cluster_with_exact_subgroups(report):
    cluster = clusters_by_member(report)[frozenset(TOTAL_SHAPE_MEMBERS)]
    assert cluster["occurrences"] == 5
    assert [g["count"] for g in cluster["exact_groups"]] == [4, 1]
    odd = cluster["exact_groups"][1]["members"]
    assert [cluster["members"][i]["qualname"] for i in odd] == ["sum_large"]
    assert cluster["id"] == "fn-" + cluster["shape_fingerprint"][:12]
    assert cluster["score"] == (5 - 1) * cluster["node_count"]
    assert cluster["distinct_files"] == 4 and cluster["distinct_inputs"] == 1


def test_decorators_dropped_from_fingerprint_but_recorded(report):
    cluster = clusters_by_member(report)[frozenset(TOTAL_SHAPE_MEMBERS)]
    members = {m["qualname"]: m for m in cluster["members"]}
    assert members["cached_total"]["decorators"] == ["functools.lru_cache(maxsize=None)"]
    assert members["cached_total"]["exact_fingerprint"] == members["total_price"]["exact_fingerprint"]


def test_true_false_none_variants_do_not_cluster(report):
    names = {m["qualname"] for c in report["function_clusters"] for m in c["members"]}
    assert not names & {"collect", "collect_strict", "collect_none"}


def test_methods_nested_and_async_functions_are_mined(tree):
    data = miner.analyze_source((tree / "app" / "orders.py").read_bytes(), MineSettings())
    found = {f["qualname"]: f for f in data["functions"]}
    assert found["Cart.total"]["kind"] == "method"
    assert found["Cart.describe"]["kind"] == "method"
    assert found["Cart.describe.<locals>.label"]["kind"] == "nested"
    assert found["fetch_all"]["async"] is True and found["fetch_all"]["kind"] == "function"
    assert found["total_price"]["top_level"] is True and found["Cart.total"]["top_level"] is False
    method_text = found["Cart.total"]["shape_text"]
    assert method_text.startswith("def f0(self, v0):") and "self.threshold" in method_text


def test_nested_function_keeps_enclosing_names_unrenamed():
    code = b"def outer(factor):\n    def inner(x):\n        y = x * factor\n        return y + y + y\n    return inner\n"
    found = {f["qualname"]: f for f in miner.analyze_source(code, MineSettings())["functions"]}
    assert "v0 * factor" in found["outer.<locals>.inner"]["shape_text"]


def test_min_occurrences_and_deterministic_ranking():
    three = run(settings=MineSettings(min_occurrences=3)).report["function_clusters"]
    assert [c["occurrences"] for c in three] == [5]  # the pair of binary searches is gone
    assert run(settings=MineSettings(min_occurrences=6)).report["function_clusters"] == []
    two = run().report["function_clusters"]
    assert [c["score"] for c in two] == sorted((c["score"] for c in two), reverse=True)
    assert [c["id"] for c in two] == [c["id"] for c in run().report["function_clusters"]]


def test_min_nodes_filter(report):
    small = run(settings=MineSettings(min_occurrences=2, min_nodes=500)).report
    assert small["function_clusters"] == []
    assert small["stats"]["functions_filtered"]["too_small"] > 0
    assert run(settings=MineSettings(min_occurrences=2, min_nodes=0)).report["stats"][
        "functions_mined"
    ] >= report["stats"]["functions_mined"]


# Filters --------------------------------------------------------------------- #
def mined_paths(rep):
    skipped = {s["path"] for s in rep["skipped_files"]}
    return skipped, {m["path"] for c in rep["function_clusters"] for m in c["members"]}


def test_test_files_skipped_unless_included():
    skipped, _ = mined_paths(run().report)
    assert {"app/test_orders.py", "app/tests/helpers.py", "app/conftest.py"} <= skipped
    _, mined = mined_paths(run(settings=MineSettings(min_occurrences=2, include_tests=True)).report)
    assert {"app/test_orders.py", "app/tests/helpers.py", "app/conftest.py"} <= mined


def test_generated_files_skipped_unless_included(report):
    assert {"path": "app/generated_pb.py", "reason": "generated"}.items() <= next(
        s for s in report["skipped_files"] if s["path"] == "app/generated_pb.py"
    ).items()
    _, mined = mined_paths(run(settings=MineSettings(min_occurrences=2, include_generated=True)).report)
    assert "app/generated_pb.py" in mined


def test_default_skip_dirs_unless_disabled(report):
    assert report["stats"]["files_seen"] == 11  # vendor/ is pruned
    _, mined = mined_paths(run(settings=MineSettings(min_occurrences=2, skip_dirs=False)).report)
    assert "app/vendor/lib.py" in mined


def test_trivial_bodies_filtered_unless_included(report):
    assert report["stats"]["functions_filtered"]["trivial_body"] == 4
    rep = run(settings=MineSettings(min_occurrences=1, include_trivial=True, min_nodes=0)).report
    assert "trivial_body" not in rep["stats"]["functions_filtered"]
    names = {m["qualname"] for c in rep["function_clusters"] for m in c["members"]}
    assert {"nothing", "answer", "fail", "stub"} <= names


def test_exclude_globs(report):
    rep = run(settings=MineSettings(min_occurrences=2, excludes=("legacy_*.py", "app/billing.py"))).report
    skipped, mined = mined_paths(rep)
    assert {"app/legacy_module.py", "app/billing.py"} <= skipped
    assert not {"app/legacy_module.py", "app/billing.py"} & mined
    assert rep["stats"]["files_skipped"]["excluded"] == 2


def test_unparseable_file_is_listed_and_run_succeeds(report):
    broken = next(s for s in report["skipped_files"] if s["path"] == "app/broken.py")
    assert broken["reason"] == "parse_error" and "line 1" in broken["error"]
    assert report["function_clusters"]


def test_function_that_cannot_canonicalize_is_filtered_not_fatal():
    code = b"def f(x):\n    class Local:\n        pass\n    return [Local() for _ in range(x)]\n"
    data = miner.analyze_source(code, MineSettings())
    assert "class definitions inside functions" in data["functions"][0]["error"]


# Coverage ---------------------------------------------------------------------- #
def test_catalog_coverage_exact_and_near(report):
    cov = report["coverage"]
    assert cov["catalog_patterns"] == 6
    assert cov["covered"] == 1 and cov["near_covered"] == 1
    assert cov["covered_percent"] == round(100 / cov["functions"], 2)
    row = next(p for p in cov["patterns"] if p["pattern"] == "search.binary_search.iterative@v1")
    assert row == {"pattern": "search.binary_search.iterative@v1", "covered": 1, "near_covered": 1}
    cluster = clusters_by_member(report)[frozenset({"find_index", "find_index_or_minus_two"})]
    assert cluster["catalog_matches"] == [
        {"pattern": "search.binary_search.iterative@v1", "match": "exact"}
    ]


def test_coverage_without_catalog():
    cov = run(catalog_root=None).report["coverage"]
    assert cov["catalog_patterns"] == 0 and cov["covered"] == 0 and cov["patterns"] == []


# Report determinism, cache, HTML ------------------------------------------------- #
def test_report_is_byte_identical_across_runs_and_jobs(tree, tmp_path):
    texts = []
    for jobs, cache in [(1, None), (1, None), (4, None), (4, str(tmp_path / "c")), (1, str(tmp_path / "c"))]:
        rep = run([str(tree)], jobs=jobs, cache_dir=cache).report
        texts.append(miner.report_json_text(rep))
    assert len(set(texts)) == 1
    data = json.loads(texts[0])
    assert data["canonical_version"] == canonical.CANONICAL_VERSION
    assert data["shape_version"] == shape.SHAPE_VERSION
    assert "jobs" not in data["settings"] and data["settings"]["min_occurrences"] == 2
    assert str(tmp_path) not in texts[0].replace(str(tree), "<input>")  # no stray absolute paths


def test_cache_used_and_invalidated(tree, tmp_path):
    cache = str(tmp_path / "cache")
    first = run([str(tree)], cache_dir=cache)
    assert first.cache_hits == 0 and first.cache_misses == 8
    second = run([str(tree)], cache_dir=cache)
    assert second.cache_hits == 8 and second.cache_misses == 0
    assert miner.report_json_text(first.report) == miner.report_json_text(second.report)
    billing = tree / "app" / "billing.py"
    billing.write_text(billing.read_text().replace("> 100", "> 7"))
    third = run([str(tree)], cache_dir=cache)
    assert third.cache_hits == 7 and third.cache_misses == 1
    cluster = clusters_by_member(third.report)[frozenset(TOTAL_SHAPE_MEMBERS)]
    assert [g["count"] for g in cluster["exact_groups"]] == [3, 1, 1]


def test_html_report_self_contained(tmp_path, report):
    json_path, html_path = miner.write_report(report, tmp_path / "out")
    html = html_path.read_text()
    for cluster in [*report["function_clusters"], *report["fragment_clusters"]]:
        assert cluster["id"] in html
    assert "http://" not in html and "https://" not in html
    assert "<script" not in html and "@import" not in html and " src=" not in html
    assert 'name="viewport"' in html
    assert json.loads(json_path.read_text()) == report


def test_inputs_record_git_commit_and_tag(tmp_path):
    import subprocess

    repo = tmp_path / "repo"
    shutil.copytree(FIXTURES / "app", repo)
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "x"], check=True)
    subprocess.run([*git, "tag", "v9.9"], check=True)
    rep = run([str(repo), str(FIXTURES)]).report
    assert rep["inputs"][0]["git"]["tag"] == "v9.9" and len(rep["inputs"][0]["git"]["commit"]) == 40
    assert rep["inputs"][1]["git"] is None  # a subfolder of a repo is not recorded


def test_cli_mine_writes_both_reports(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        app, ["--root", str(REPO_ROOT), "mine", str(FIXTURES), "--out", str(tmp_path / "r")]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "r" / "report.json").is_file() and (tmp_path / "r" / "report.html").is_file()
    assert "functions: 14 mined of 18 found" in result.output
    assert (tmp_path / ".pcat-cache").is_dir()


def test_cli_mine_missing_input(tmp_path):
    result = CliRunner().invoke(app, ["mine", str(tmp_path / "nope"), "--out", str(tmp_path / "r")])
    assert result.exit_code == 1 and "does not exist" in result.output
