"""v5.1 Part B: check_code on partial code (a function without its imports)."""

from __future__ import annotations

import pytest

from conftest import REPO_ROOT
from pcat.serving import CatalogService

HTTP = "http.get_with_retry.requests"
GUARDED = {"PC100", "PC101", "PC103", "PC105"}


@pytest.fixture(scope="module")
def service() -> CatalogService:
    return CatalogService(REPO_ROOT)


@pytest.fixture(scope="module")
def full_code(service) -> str:
    return service.get_pattern(HTTP, {"f0": "fetch"})["code"]


def strip_imports(code: str) -> str:
    return "\n".join(ln for ln in code.splitlines() if not ln.startswith(("import ", "from "))) + "\n"


def analysis(result: dict) -> dict:
    [a] = result["deviations"]
    return a


def codes(a: dict) -> set[str]:
    return {d["code"] for d in a["deviations"]}


def test_full_file_resolution_is_full_and_unchanged(service, full_code):
    a = analysis(service.check_code(full_code, HTTP))
    assert a["resolution"] == "full" and a["unknown_names"] == [] and a["skipped_rules"] == []
    assert a["deviations"] == []


def test_snippet_without_imports_reports_no_library_swap_or_missing_calls(service, full_code):
    result = service.check_code(strip_imports(full_code), HTTP)
    a = analysis(result)
    assert a["resolution"] == "partial" and result["resolution"] == "partial"
    assert a["unknown_names"] == ["random", "requests", "time"]
    assert a["assumed"] == {"random": "random", "requests": "requests", "time": "time"}
    assert a["deviations"] == [] and "context" in result["next_step"]


def test_unknown_alias_skips_the_rules_that_depend_on_it(service, full_code):
    snippet = strip_imports(full_code).replace("requests.", "rq.")
    a = analysis(service.check_code(snippet, HTTP))
    assert not codes(a) & GUARDED
    assert all(d["severity"] != "high" for d in a["deviations"])
    assert "rq" in a["unknown_names"] and "rq" not in a["assumed"]
    skipped = " ".join(a["skipped_rules"])
    assert "PC103" in skipped and "PC105" in skipped and "must_catch `requests.ConnectionError`" in skipped


def test_context_restores_full_resolution(service, full_code):
    snippet = strip_imports(full_code).replace("requests.", "rq.")
    a = analysis(service.check_code(snippet, HTTP, context="import random\nimport requests as rq\nimport time\n"))
    assert a["resolution"] == "full" and a["skipped_rules"] == [] and a["deviations"] == []


def test_context_with_a_genuine_swap_is_still_reported(service, full_code):
    snippet = strip_imports(full_code)
    a = analysis(service.check_code(snippet, HTTP, context="import random\nimport httpx as requests\nimport time\n"))
    assert a["resolution"] == "full" and "PC103" in codes(a)


def test_context_that_does_not_parse_uses_its_import_lines(service, full_code):
    broken = "import random\nimport requests as rq\nimport time\n\ndef half(:\n"
    result = service.check_code(strip_imports(full_code).replace("requests.", "rq."), HTTP, context=broken)
    assert analysis(result)["resolution"] == "full" and "import lines only" in result["context_notes"][0]


def test_missing_call_is_still_reported_when_nothing_could_be_it(service, full_code):
    snippet = strip_imports(full_code).replace("                response.raise_for_status()\n", "")
    a = analysis(service.check_code(snippet, HTTP))
    assert "PC100" in codes(a) and a["resolution"] == "partial"  # guard must_call .raise_for_status
    assert any("raise_for_status" in d["message"] for d in a["deviations"])


def test_file_path_inside_the_repo_is_read(tmp_path, full_code):
    pkg = tmp_path / "app"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "client.py").write_text("import random\nimport requests as rq\nimport time\n")
    service = CatalogService(REPO_ROOT, repo=tmp_path)
    snippet = strip_imports(full_code).replace("requests.", "rq.")
    result = service.check_code(snippet, HTTP, file_path="app/client.py")
    assert analysis(result)["resolution"] == "full" and "context_notes" not in result
    outside = service.check_code(snippet, HTTP, file_path="../../etc/passwd")
    assert analysis(outside)["resolution"] == "partial" and "not a file inside" in outside["context_notes"][0]
    no_repo = CatalogService(REPO_ROOT).check_code(snippet, HTTP, file_path="app/client.py")
    assert "context_notes" in no_repo


def test_instructions_mention_context(service):
    assert "`context`" in service.instructions() and "file_path" in service.instructions()
