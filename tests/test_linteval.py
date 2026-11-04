"""v4 evaluation scoring on small fixtures (no `claude -p` calls)."""

from __future__ import annotations

from pcat import linteval


def dev(code, severity, approved=False):
    return {"code": code, "severity": severity, "approved": approved}


def test_fetched_patterns_dedupes_and_skips_errors():
    calls = [
        {"tool": "search_patterns", "arguments": {"request": "x"}, "result": {}},
        {"tool": "get_pattern", "arguments": {"id": "a.b"}, "result": {"id": "a.b@v1", "status": "active"}},
        {"tool": "get_pattern", "arguments": {"id": "nope.x"}, "result": {"error": "unknown id"}},
        {"tool": "get_pattern", "arguments": {"id": "a.b@v1"}, "result": {"id": "a.b@v1"}},
        {"tool": "get_pattern", "arguments": {"id": "c.d"}, "result": {"id": "c.d@v2"}},
    ]
    assert linteval.fetched_patterns(calls) == ["a.b", "c.d"]


def test_worst_codes_and_high_codes():
    analyses = [{"deviations": [dev("PC109", "low"), dev("PC100", "high", approved=True)]},
                {"deviations": [dev("PC106", "medium")]}]
    assert linteval.worst(analyses) == "medium"
    assert linteval.worst(analyses, approved=True) == "high"
    assert linteval.worst([]) == "none"
    assert linteval.codes(analyses) == ["PC100", "PC106", "PC109"]
    assert linteval.high_codes(analyses) == ["PC100"]


def row(task, outcome, codes, worst, high=(), switched=False):
    return {"task": task, "outcome": outcome, "codes": list(codes), "worst": worst,
            "high_codes": list(high), "switched_library": switched}


def test_confusion_and_replay_checks():
    rows = [
        row("jwt_create", "matched", [], "none"),
        row("http_retry", "matched", ["PC109"], "low"),
        row("http_retry", "matched", ["PC106"], "medium"),
        row("http_retry", "fetched_but_changed", ["PC100"], "high", ["PC100"]),
        row("paginate_query", "fetched_but_changed", ["PC107"], "medium"),
        row("csv_import", "fetched_but_changed", ["PC103"], "high", ["PC103"], switched=True),
        row("csv_import", "fetched_but_changed", [], "none"),
    ]
    table = linteval.confusion(rows)
    assert table["matched"] == {"none": 1, "low": 1, "medium": 1, "high": 0}
    assert table["fetched_but_changed"] == {"none": 1, "low": 0, "medium": 1, "high": 2}
    checks = linteval.replay_checks(rows)
    assert checks["exact_with_deviation_other_than_PC109"] == 1 and checks["exact_flagged_above_low"] == 1
    assert checks["misses_with_a_deviation"] == 3 and checks["misses"] == 4
    assert checks["http_misses_high_PC100_or_PC101"] == 1
    assert checks["pagination_misses_with_PC106"] == 0
    assert (checks["csv_misses_switched_library"], checks["csv_switched_with_PC103"]) == (1, 1)


def test_approval_census_and_worst_not_proposed():
    import ast

    from pcat import provenance

    body = "def f(x):\n    return x + 1\n"
    h = provenance.function_hash(ast.parse(body).body[0])
    code = (f"# pcat-allow: PC100 #{h} -- the request needs this change\n"
            "# pcat-allow: PC101 #00000000 -- written for some older code\n"
            "# pcat-allow: PC109 -- v4 style approval without a hash\n"
            "# pcat-allow: PC105 -- short\n" + body)
    states = [(a["code"], a["state"]) for a in linteval.approval_census(code)]
    assert states == [("PC100", "confirmable"), ("PC101", "stale_hash"), ("PC109", "no_hash"), ("PC105", "invalid")]
    analyses = [{"deviations": [{"severity": "high", "approved": False, "approval_state": "proposed"},
                                {"severity": "medium", "approved": False, "approval_state": None}]}]
    assert linteval.worst_not_proposed(analyses) == "medium" and linteval.worst(analyses) == "high"
