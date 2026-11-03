"""Catalog tools behind `pcat serve` (no MCP SDK needed)."""

from __future__ import annotations

import json

import pytest

from conftest import REPO_ROOT, edit_yaml, pattern_dir
from pcat import catalog as cat
from pcat.errors import PcatError
from pcat.serving import NO_MATCH_MESSAGE, CatalogService

PBKDF2 = "auth.password.pbkdf2"


@pytest.fixture(scope="module")
def service():
    return CatalogService(REPO_ROOT)


def test_instructions_list_catalog_categories(service):
    text = service.instructions()
    for category in ("auth", "db", "http", "config", "ratelimit", "importers"):
        assert f"{category}:" in text
    assert "search_patterns" in text and "get_pattern" in text and "check_code" in text


def test_search_returns_fields_and_is_deterministic(service):
    first = service.search_patterns("store a user's password securely and check it at login")
    assert first == service.search_patterns("store a user's password securely and check it at login")
    top = first["matches"][0]
    assert top["id"] == PBKDF2 and top["exports"] == ["verify_password", "needs_rehash"]
    assert set(top) == {"id", "version", "title", "summary", "use_when", "score", "requires", "exports"}
    json.dumps(first)  # JSON-serializable


def test_search_with_no_match(service):
    result = service.search_patterns("zzqv xylophone")
    assert result == {"matches": [], "message": NO_MATCH_MESSAGE}


def test_search_validates_request_and_limit(service):
    with pytest.raises(PcatError):
        service.search_patterns("   ")
    assert len(service.search_patterns("token", limit=1)["matches"]) <= 1


def test_get_pattern_default_names(service):
    result = service.get_pattern(PBKDF2)
    assert result["entry_point"] == "hash_password" and result["requires"] == []
    assert "def hash_password(" in result["code"] and "def verify_password(" in result["code"]
    assert result["names"]["f0"] == "hash_password" and "warning" not in result
    assert result["usage"] and result["version"] == 1 and result["status"] == "active"
    json.dumps(result)


def test_get_pattern_with_caller_names(service):
    result = service.get_pattern("auth.jwt.create_access_token", {"f0": "issue_token", "v0": "account_id"})
    assert "def issue_token(account_id" in result["code"] and result["entry_point"] == "issue_token"
    assert result["requires"] == ["pyjwt>=2.8,<3"]


def test_get_pattern_invalid_name_keys_list_valid_ones(service):
    with pytest.raises(PcatError) as info:
        service.get_pattern(PBKDF2, {"bogus": "x"})
    assert "invalid name keys ['bogus']" in str(info.value) and "f0 (hash_password)" in str(info.value)


def test_get_pattern_name_collision_rejected(service):
    with pytest.raises(PcatError, match="collide"):
        service.get_pattern("search.binary_search.iterative", {"v0": "len"})


def test_get_pattern_unknown_id(service):
    with pytest.raises(PcatError, match="unknown pattern id 'nope.nothing'.*auth.jwt.create_access_token"):
        service.get_pattern("nope.nothing")


def test_get_pattern_deprecated_warning(root):
    edit_yaml(pattern_dir(root, "search.binary_search.recursive"), status="deprecated",
              replaced_by="search.binary_search.iterative")
    cat.write_index(root)
    result = CatalogService(root).get_pattern("search.binary_search.recursive")
    assert result["status"] == "deprecated"
    assert result["warning"] == ("search.binary_search.recursive@v1 is deprecated; "
                                 "use search.binary_search.iterative instead")


def test_check_code_covered_near_and_none(service):
    code = service.get_pattern(PBKDF2, {"f0": "make_hash"})["code"]
    code = code.replace("make_hash", "hash_password")
    near = code.replace("SALT_BYTES = 16", "SALT_BYTES = 16").replace("'sha256'", "'sha512'")
    extra = "\n\ndef unrelated(x):\n    return [x, x, x, x, x, x, x, x]\n"
    result = service.check_code(code + extra)
    statuses = {f["name"]: (f["status"], f["pattern"], f["pattern_function"]) for f in result["functions"]}
    assert statuses["hash_password"] == ("covered", PBKDF2, "hash_password")
    assert statuses["verify_password"] == ("covered", PBKDF2, "verify_password")
    assert statuses["needs_rehash"] == ("covered", PBKDF2, "needs_rehash")
    assert statuses["unrelated"] == ("none", None, None)
    assert result["summary"] == {"covered": 3, "near": 0, "none": 1}
    near_statuses = {f["name"]: f["status"] for f in service.check_code(near)["functions"]}
    assert near_statuses["hash_password"] == "near" and near_statuses["verify_password"] == "near"


def test_check_code_syntax_error_is_a_result_not_an_exception(service):
    result = service.check_code("def broken(:\n    pass\n")
    assert result["functions"] == [] and result["error"].startswith("syntax error at line 1")


def test_tool_calls_are_logged(tmp_path):
    log = tmp_path / "calls.jsonl"
    svc = CatalogService(REPO_ROOT, log)
    svc.search_patterns("paginate a sqlalchemy query")
    svc.get_pattern("db.pagination.select_page")
    svc.check_code("x = (")
    with pytest.raises(PcatError):
        svc.get_pattern("nope.nothing")
    lines = [json.loads(line) for line in log.read_text().splitlines()]
    assert [line["tool"] for line in lines] == ["search_patterns", "get_pattern", "check_code", "get_pattern"]
    assert lines[0]["arguments"]["request"] == "paginate a sqlalchemy query"
    assert lines[0]["result"]["ids"][0] == "db.pagination.select_page"
    assert lines[3]["result"] == {"error": "unknown id"}
    assert all(line["timestamp"].endswith("+00:00") for line in lines)
