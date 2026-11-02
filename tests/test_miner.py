"""Miner: discovery, filters, function clusters, coverage, report, cache."""

from __future__ import annotations

import ast
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
    assert report["stats"]["files_seen"] == 12  # vendor/ is pruned
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
    assert first.cache_hits == 0 and first.cache_misses == 9
    second = run([str(tree)], cache_dir=cache)
    assert second.cache_hits == 9 and second.cache_misses == 0
    assert miner.report_json_text(first.report) == miner.report_json_text(second.report)
    billing = tree / "app" / "billing.py"
    billing.write_text(billing.read_text().replace("> 100", "> 7"))
    third = run([str(tree)], cache_dir=cache)
    assert third.cache_hits == 8 and third.cache_misses == 1
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
    assert "functions: 17 mined of 21 found" in result.output
    assert (tmp_path / ".pcat-cache").is_dir()


def test_cli_mine_missing_input(tmp_path):
    result = CliRunner().invoke(app, ["mine", str(tmp_path / "nope"), "--out", str(tmp_path / "r")])
    assert result.exit_code == 1 and "does not exist" in result.output


# Part B: fragments ----------------------------------------------------------- #
def fragment_clusters(rep):
    return rep["fragment_clusters"]


def test_fragment_cluster_found_and_renamed(report):
    (cluster,) = [c for c in fragment_clusters(report) if c["members"][0]["statement"] == "for"]
    assert cluster["id"].startswith("fr-") and cluster["id"] == "fr-" + cluster["shape_fingerprint"][:12]
    assert [(m["qualname"], m["statement"]) for m in cluster["members"]] == [
        ("parse_ini", "for"), ("parse_env", "for"), ("Loader.load", "for"),
    ]
    text = cluster["shape_text"]
    assert text.startswith("for v0 in v1:\n    v2 = v0.strip()")  # parameter/locals renamed
    assert "v3 in RESERVED" in text  # global left alone
    assert "int(v4.strip())" in text and "except ValueError:" in text  # builtins left alone
    assert [g["count"] for g in cluster["exact_groups"]] == [2, 1]  # '=' vs ':' separator


def test_parameter_renamed_global_not():
    code = (
        b"LIMIT = 3\n"
        b"def f(items, extra):\n"
        b"    out = []\n"
        b"    for x in items:\n"
        b"        if x > LIMIT and x not in extra:\n"
        b"            out.append(x * x + LIMIT)\n"
        b"            print(out, len(out))\n"
        b"    return out\n"
    )
    (frag,) = [
        f for f in miner.analyze_source(code, MineSettings(min_fragment_nodes=10))["fragments"]
        if f["statement"] == "for"
    ]
    assert frag["shape_text"].startswith("for v0 in v1:\n    if v0 > LIMIT and v0 not in v2:")
    assert "v3.append(v0 * v0 + LIMIT)" in frag["shape_text"]


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text)
    return path


LOOP = """
    for raw in lines:
        line = raw.strip()
        try:
            key, value = line.split("=", 1)
            result[key.strip().lower()] = int(value.strip())
        except ValueError:
            errors.append(line)
            continue
"""


def test_whole_body_fragments_are_dropped(tmp_path):
    funcs = "".join(f"\n\ndef parse_{i}(lines, result, errors):{LOOP}" for i in range(3))
    _write(tmp_path, "m.py", funcs)
    rep = run([str(tmp_path)], catalog_root=None, settings=MineSettings(min_occurrences=3)).report
    statements = {m["statement"] for c in rep["fragment_clusters"] for m in c["members"]}
    assert "for" not in statements  # each for loop is an entire function body
    assert statements == {"try"}  # the inner try is not, so it still clusters


def test_contained_cluster_suppressed_only_with_same_occurrences(tmp_path):
    body = "\n    total = 0" + LOOP + "    return total\n"
    funcs = "".join(f"\n\ndef parse_{i}(lines, result, errors):{body}" for i in range(3))
    _write(tmp_path, "m.py", funcs)
    rep = run([str(tmp_path)], catalog_root=None, settings=MineSettings(min_occurrences=3)).report
    assert [c["members"][0]["statement"] for c in rep["fragment_clusters"]] == ["for"]

    # A fourth occurrence of the try block alone: occurrences differ, both reported.
    extra = (
        "\n\ndef single(line, result, errors):\n    while line:\n"
        + "\n".join(ln for ln in LOOP.splitlines()[3:])
        + "\n        break\n    return result\n"
    )
    _write(tmp_path, "n.py", extra)
    rep = run([str(tmp_path)], catalog_root=None, settings=MineSettings(min_occurrences=3)).report
    kinds = sorted((c["members"][0]["statement"], c["occurrences"]) for c in rep["fragment_clusters"])
    assert kinds == [("for", 3), ("try", 4)]


def test_elif_chain_is_one_fragment():
    tree = ast.parse(
        "def f(x):\n    if x == 1:\n        a = 1\n    elif x == 2:\n        a = 2\n    else:\n"
        "        if x:\n            a = 3\n        a = 4\n    return a\n"
    )
    found = list(miner._candidate_statements(tree.body[0]))
    # the outer if, plus the `if x:` nested in the else (it is not the sole else statement)
    assert [(type(n).__name__, n.lineno) for n in found] == [("If", 2), ("If", 7)]


def test_nested_function_fragments_belong_to_inner_function():
    code = (
        b"def outer(rows):\n"
        b"    def inner(items):\n"
        b"        acc = []\n"
        b"        for i in items:\n"
        b"            if i is not None:\n"
        b"                acc.append(i * 2 + 1)\n"
        b"                acc.sort()\n"
        b"        return acc\n"
        b"    return inner(rows)\n"
    )
    frags = miner.analyze_source(code, MineSettings(min_fragment_nodes=5))["fragments"]
    assert {f["qualname"] for f in frags} == {"outer.<locals>.inner"}


def test_no_fragments_flag(report):
    rep = run(settings=MineSettings(min_occurrences=2, fragments=False)).report
    assert rep["fragment_clusters"] == [] and rep["stats"]["fragments_mined"] == 0
    assert rep["function_clusters"] == report["function_clusters"]


def test_min_fragment_nodes(report):
    rep = run(settings=MineSettings(min_occurrences=2, min_fragment_nodes=1000)).report
    assert rep["fragment_clusters"] == []
    assert report["stats"]["fragments_mined"] > 0


# Part C: promote ------------------------------------------------------------ #
@pytest.fixture
def mined(tree, tmp_path, root):
    """A report over a temp copy of the fixtures, plus a temp catalog root."""
    rep = run([str(tree)], catalog_root=root).report
    json_path, _ = miner.write_report(rep, tmp_path / "out")
    return rep, json_path, root


def promote(root, *args):
    return CliRunner().invoke(app, ["--root", str(root), "promote", *map(str, args)])


def total_cluster(rep):
    return clusters_by_member(rep)[frozenset(TOTAL_SHAPE_MEMBERS)]


def test_promote_creates_valid_pattern_from_representative(mined):
    rep, json_path, root = mined
    cluster = total_cluster(rep)
    assert miner.representative(cluster)["qualname"] == "total_price"  # orders.py is shortest
    result = promote(root, cluster["id"], "--report", json_path, "--id", "billing.total_price.doubled")
    assert result.exit_code == 0, result.output
    assert "promoting total_price" in result.output
    folder = root / "catalog" / "billing" / "total_price.doubled"
    impl = (folder / "impl.py").read_text()
    assert canonical.list_functions(impl) == ["total_price"]
    assert "import asyncio" not in impl  # only what the function uses
    (folder / "test_impl.py").write_text(
        "from types import SimpleNamespace as N\n\nfrom impl import total_price\n\n\n"
        "def test_total():\n    assert total_price([N(price=150), N(price=50)]) == 300\n\n\n"
        "def test_empty():\n    assert total_price([]) == 0\n"
    )
    assert CliRunner().invoke(app, ["--root", str(root), "index"]).exit_code == 0
    result = CliRunner().invoke(app, ["--root", str(root), "validate", "billing.total_price.doubled"])
    assert result.exit_code == 0, result.output


def test_promote_specific_member(mined):
    rep, json_path, root = mined
    cluster = total_cluster(rep)
    idx = next(m["index"] for m in cluster["members"] if m["qualname"] == "sum_large")
    result = promote(root, cluster["id"], "--report", json_path, "--id", "billing.sum_large.x", "--member", idx)
    assert result.exit_code == 0, result.output
    impl = (root / "catalog" / "billing" / "sum_large.x" / "impl.py").read_text()
    assert "def sum_large(rows):" in impl
    bad = promote(root, cluster["id"], "--report", json_path, "--id", "billing.y.z", "--member", 99)
    assert bad.exit_code == 1 and "out of range" in bad.output


def test_promote_rejects_fragment_cluster_with_location(mined):
    rep, json_path, root = mined
    frag = next(c for c in rep["fragment_clusters"] if c["members"][0]["statement"] == "for")
    result = promote(root, frag["id"], "--report", json_path, "--id", "text.x.y")
    assert result.exit_code == 1
    assert "fragments can't be promoted yet" in result.output
    assert "app/config.py:" in result.output  # where to extract it by hand
    assert not (root / "catalog" / "text" / "x.y").exists()


def test_promote_rejects_methods(tmp_path, root):
    method = "    def total(self, items):\n        t = 0\n        for i in items:\n            if i.p > 1:\n                t += i.p * 2\n        return t\n"
    src = tmp_path / "methods"
    src.mkdir()
    (src / "m.py").write_text("".join(f"class C{i}:\n{method}\n\n" for i in range(3)))
    rep = run([str(src)], catalog_root=root).report
    json_path, _ = miner.write_report(rep, tmp_path / "out")
    (cluster,) = rep["function_clusters"]
    result = promote(root, cluster["id"], "--report", json_path, "--id", "x.y.z")
    assert result.exit_code == 1
    assert "C0.total" in result.output and "is a method" in result.output


def test_promote_rejects_changed_source(mined, tree):
    rep, json_path, root = mined
    orders = tree / "app" / "orders.py"
    orders.write_text(orders.read_text() + "\n# touched\n")
    result = promote(root, total_cluster(rep)["id"], "--report", json_path, "--id", "billing.a.b")
    assert result.exit_code == 1 and "changed since it was mined" in result.output
    assert "re-run `pcat mine`" in result.output


def test_promote_missing_report_or_cluster(mined, tmp_path):
    _, json_path, root = mined
    missing = promote(root, "fn-000000000000", "--report", tmp_path / "nope.json", "--id", "a.b.c")
    assert missing.exit_code == 1 and "not found" in missing.output
    unknown = promote(root, "fn-000000000000", "--report", json_path, "--id", "a.b.c")
    assert unknown.exit_code == 1 and "is not in" in unknown.output
