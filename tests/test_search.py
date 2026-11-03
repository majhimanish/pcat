"""BM25 catalog search."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from conftest import REPO_ROOT, edit_yaml, pattern_dir
from pcat import catalog as cat
from pcat import search
from pcat.cli import app


@pytest.mark.parametrize("text,tokens", [
    ("Hash the PASSWORD", ["hash", "password"]),
    ("auth.jwt.create_access_token", ["auth", "jwt", "access", "token"]),
    ("tokens hashing hashed limited", ["token", "hash", "hash", "limit"]),
    ("paginate pagination paginated", ["pagin", "pagin", "pagin"]),
    ("libraries queries", ["library", "query"]),
    ("access class process", ["access", "class", "process"]),
    ("is it a CSV? (yes) 2-factor", ["csv", "yes", "2", "factor"]),
    ("", []),
])
def test_tokenizer(text, tokens):
    assert search.tokenize(text) == tokens


def test_stemming_keeps_short_stems():
    assert search.stem("uses") == "use" and search.stem("bed") == "bed" and search.stem("is") == "is"


def index(root=REPO_ROOT, **kw):
    return search.SearchIndex.from_root(root, **kw)


def test_ranking_is_deterministic_and_sorted():
    a = index().rank("hash a password and verify it at login")
    b = index().rank("hash a password and verify it at login")
    assert [(h.id, h.score) for h in a] == [(h.id, h.score) for h in b]
    assert a[0].id == "auth.password.pbkdf2"
    assert [h.score for h in a] == sorted((h.score for h in a), reverse=True)


def test_ties_are_broken_by_id():
    hits = index().rank("binary search sorted list index")
    tied = [h for h in hits if h.id.startswith("search.binary_search")]
    assert [h.id for h in tied] == sorted(h.id for h in tied)


def test_threshold_and_limit():
    idx = index()
    assert idx.search("retry an http get request", limit=1, threshold=0.0)[0].id == \
        "http.get_with_retry.requests"
    assert idx.search("retry an http get request", threshold=1e9) == []
    assert len(idx.search("token", limit=2, threshold=0.0)) <= 2
    assert idx.search("token", limit=0, threshold=0.0) == []


def test_unknown_words_score_nothing():
    assert index().rank("zzqv xylophone") == []
    assert index().rank("the and of") == []  # only stop words


def test_deprecated_patterns_excluded_unless_asked(root):
    edit_yaml(pattern_dir(root, "search.binary_search.recursive"), status="deprecated",
              replaced_by="search.binary_search.iterative")
    cat.write_index(root)
    ids = {h.id for h in index(root).rank("binary search recursive")}
    assert "search.binary_search.recursive" not in ids
    assert "search.binary_search.recursive" in {
        h.id for h in index(root, include_deprecated=True).rank("binary search recursive")}


def test_cli_search(root):
    out = CliRunner().invoke(app, ["--root", str(root), "search", "import users from a csv file"])
    assert out.exit_code == 0 and out.output.splitlines()[0].startswith("importers.users_csv.parse")
    none = CliRunner().invoke(app, ["--root", str(root), "search", "zzqv xylophone"])
    assert none.exit_code == 0 and "no reviewed pattern fits" in none.output
