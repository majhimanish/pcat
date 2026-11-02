"""End-to-end tests of the `pcat` commands."""

from __future__ import annotations

import json
import re
import textwrap

import pytest
import yaml
from typer.testing import CliRunner

from conftest import REPO_ROOT, SEED_IDS, edit_yaml, pattern_dir
from pcat import canonical
from pcat import catalog as cat
from pcat.cli import app

runner = CliRunner()
ITER = "search.binary_search.iterative"


def pcat(root, *args):
    return runner.invoke(app, ["--root", str(root), *map(str, args)])


MULTI = textwrap.dedent(
    '''
    import json
    import os
    from collections import Counter


    def unrelated(path):
        return os.path.exists(path)


    def _normalize(word):
        # lowercase and strip punctuation
        return word.strip(".,!?").lower()


    def _tokens(text):
        return [_normalize(w) for w in text.split()]


    def top_words(text, n):
        """Return the n most common words in text."""
        return [w for w, _ in Counter(_tokens(text)).most_common(n)]


    def dump(data):
        return json.dumps(data)
    '''
).lstrip()


def test_new_scaffolds_pattern(root):
    result = pcat(root, "new", "text.word_count.simple")
    assert result.exit_code == 0, result.output
    folder = pattern_dir(root, "text.word_count.simple")
    assert {p.name for p in folder.iterdir()} == {"pattern.yaml", "impl.py", "test_impl.py"}
    meta, errors = cat.parse_meta((folder / "pattern.yaml").read_text())
    assert errors == []
    assert meta.variant_of == "text.word_count" and meta.entry_point == "word_count"
    assert canonical.list_functions((folder / "impl.py").read_text()) == ["word_count"]


def test_new_rejects_existing_and_bad_ids(root):
    assert pcat(root, "new", ITER).exit_code == 1
    result = pcat(root, "new", "Bad-Id")
    assert result.exit_code == 1 and "invalid id" in result.output


def test_new_pattern_fails_validation_until_completed(root):
    pcat(root, "new", "text.word_count.simple")
    pcat(root, "index")
    result = pcat(root, "validate", "text.word_count.simple")
    assert result.exit_code == 1
    assert "[check 4]" in result.output and "[check 8]" in result.output


def test_add_extracts_function_and_helpers(root, tmp_path):
    source = tmp_path / "words.py"
    source.write_text(MULTI)
    result = pcat(root, "add", source, "--function", "top_words", "--id", "text.top_words.counter")
    assert result.exit_code == 0, result.output
    assert "_normalize" in result.output and "_tokens" in result.output

    folder = pattern_dir(root, "text.top_words.counter")
    impl = (folder / "impl.py").read_text()
    assert canonical.list_functions(impl) == ["_normalize", "_tokens", "top_words"]
    assert "from collections import Counter" in impl
    assert "import os" not in impl and "import json" not in impl
    assert "unrelated" not in impl and "dump" not in impl
    assert "# lowercase and strip punctuation" in impl

    meta = yaml.safe_load((folder / "pattern.yaml").read_text())
    assert meta["entry_point"] == "top_words"
    assert meta["summary"] == "Return the n most common words in text."
    assert meta["fingerprint"] == canonical.analyze(impl, "top_words").fingerprint

    (folder / "test_impl.py").write_text(
        "from impl import top_words\n\n\n"
        "def test_top():\n    assert top_words('a b. A c b a', 2) == ['a', 'b']\n\n\n"
        "def test_empty():\n    assert top_words('', 3) == []\n"
    )
    assert pcat(root, "index").exit_code == 0
    result = pcat(root, "validate", "text.top_words.counter")
    assert result.exit_code == 0, result.output


def test_add_unknown_function(root, tmp_path):
    source = tmp_path / "words.py"
    source.write_text(MULTI)
    result = pcat(root, "add", source, "--function", "missing", "--id", "text.x.y")
    assert result.exit_code == 1 and "no top-level function" in result.output


def test_canonical_command(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("def helper(a):\n    return a\n\ndef main(b: int):\n    '''doc'''\n    return helper(b)\n")
    result = runner.invoke(app, ["canonical", str(f), "--entry", "main"])
    assert result.exit_code == 0
    assert result.output == "def f0(v0: int):\n    return f1(v0)\n\ndef f1(v0):\n    return v0\n"
    result = runner.invoke(app, ["canonical", str(f), "--entry", "main", "--no-annotations"])
    assert "def f0(v0):" in result.output


def test_canonical_command_reports_errors(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("X = 1\n")
    result = runner.invoke(app, ["canonical", str(f)])
    assert result.exit_code == 1 and result.output.startswith("error:")


def test_fingerprint_print_and_write(root):
    folder = pattern_dir(root, ITER)
    expected = yaml.safe_load((folder / "pattern.yaml").read_text())["fingerprint"]
    result = pcat(root, "fingerprint", ITER)
    assert result.exit_code == 0 and result.output.strip() == expected

    impl = folder / "impl.py"
    impl.write_text(impl.read_text().replace("return -1", "return -2"))
    before = (folder / "pattern.yaml").read_text()
    result = pcat(root, "fingerprint", ITER, "--write")
    new = result.output.strip()
    assert new != expected
    after = (folder / "pattern.yaml").read_text()
    assert after == before.replace(expected, new)  # only that line changed


def test_index_twice_is_byte_identical(root):
    assert pcat(root, "index").exit_code == 0
    first = (root / "catalog" / "index.json").read_bytes()
    assert pcat(root, "index").exit_code == 0
    assert (root / "catalog" / "index.json").read_bytes() == first
    assert first == (REPO_ROOT / "catalog" / "index.json").read_bytes()


def test_index_format(root):
    doc = json.loads((root / "catalog" / "index.json").read_text())
    assert list(doc) == ["canonical_version", "patterns"]
    assert doc["canonical_version"] == canonical.CANONICAL_VERSION == 2
    entries = doc["patterns"]
    assert [e["id"] for e in entries] == SEED_IDS
    assert set(entries[0]) == {
        "id", "version", "title", "category", "variant_of", "behavior", "status", "fingerprint", "path",
    }
    assert entries[0]["path"] == "catalog/collections/group_by.dict_of_lists"


def test_show(root):
    result = pcat(root, "show", ITER)
    assert result.exit_code == 0
    meta_text, code = result.output.split("---\n", 1)
    assert yaml.safe_load(meta_text)["id"] == ITER
    assert "def binary_search(items: Sequence[Any], target: Any) -> int:" in code
    assert '"""' not in code


def test_show_unknown(root):
    result = pcat(root, "show", "nope.nope")
    assert result.exit_code == 1 and "unknown pattern" in result.output


def test_render_with_spec_syntax(root):
    result = pcat(root, "render", ITER, "--names", "f0=find_user", "v0=users")
    assert result.exit_code == 0, result.output
    assert "def find_user(users: Sequence[Any], target: Any) -> int:" in result.output
    assert "value = users[mid]" in result.output


def test_render_repeated_flag_and_errors(root):
    ok = pcat(root, "render", ITER, "--names", "v1=wanted", "--names", "f0.v0=xs")
    assert ok.exit_code == 0 and "def binary_search(xs: Sequence[Any], wanted: Any)" in ok.output
    assert pcat(root, "render", ITER, "--names", "v99=x").exit_code == 1
    assert pcat(root, "render", ITER, "--names", "novalue").exit_code == 1
    collide = pcat(root, "render", ITER, "--names", "v0=len")
    assert collide.exit_code == 1 and "collide" in collide.output


RENAMED_COPY = textwrap.dedent(
    """
    from typing import Any
    from collections.abc import Sequence


    def lookup(haystack: Sequence[Any], needle: Any) -> int:
        # my own copy, with different names and comments
        lo = 0
        hi = len(haystack) - 1
        while lo <= hi:
            middle = lo + (hi - lo) // 2  # overflow-safe midpoint
            candidate = haystack[middle]
            if candidate == needle: return middle
            if candidate < needle:
                lo = middle + 1
            else:
                hi = middle - 1
        return -1


    def other(x):
        return x + 1
    """
)


def test_find_reports_matching_pattern(root, tmp_path):
    candidate = tmp_path / "mine.py"
    candidate.write_text(RENAMED_COPY)
    result = pcat(root, "find", candidate)
    assert result.exit_code == 0, result.output
    assert f"lookup: {ITER}@v1 (active)" in result.output
    assert "other: no match" in result.output


def test_find_with_helper_function(root, tmp_path):
    impl = (pattern_dir(root, "search.binary_search.recursive") / "impl.py").read_text()
    candidate = tmp_path / "mine.py"
    candidate.write_text(re.sub(r"\b_search\b", "_go", impl).replace("items", "xs"))
    result = pcat(root, "find", candidate)
    assert "binary_search: search.binary_search.recursive@v1 (active)" in result.output
    assert "_go: no match" in result.output


def test_validate_command_reports_each_problem(root):
    for pid in ("search.binary_search.iterative", "text.slugify.ascii"):
        impl = pattern_dir(root, pid) / "impl.py"
        impl.write_text(impl.read_text() + "\n\ndef extra():\n    return 1\n")
    result = pcat(root, "validate", "--skip-tests")
    assert result.exit_code == 1
    lines = [line for line in result.output.splitlines() if "[check" in line]
    assert len(lines) == 2
    assert "2 problem(s) found" in result.output


@pytest.mark.parametrize("pattern_id", SEED_IDS)
def test_editing_any_seed_without_version_bump_fails(root, pattern_id):
    impl = pattern_dir(root, pattern_id) / "impl.py"
    impl.write_text(impl.read_text() + "\n\ndef _added_later():\n    return None\n")
    result = pcat(root, "validate", "--skip-tests")
    assert result.exit_code == 1
    assert f"{pattern_id}@v1: [check 4] fingerprint mismatch" in result.output


def test_missing_catalog_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["index"])
    assert result.exit_code == 1 and "no catalog/ directory" in result.output


# v1.1 ----------------------------------------------------------------------- #

GREETER = textwrap.dedent(
    '''
    import re

    UNUSED = 5
    GREETING = "hello"
    PUNCT = ".,!?"
    PATTERN = re.compile(r"\\s+")


    def _clean(word):
        return word.strip(PUNCT)


    def greet(name):
        """Greet someone politely."""
        return f"{GREETING}, {_clean(name)}"


    def squash(text):
        return PATTERN.sub(" ", text)
    '''
).lstrip()


def test_add_copies_constants_used_by_function_and_helper(root, tmp_path):
    source = tmp_path / "greeter.py"
    source.write_text(GREETER)
    result = pcat(root, "add", source, "--function", "greet", "--id", "text.greet.polite")
    assert result.exit_code == 0, result.output
    folder = pattern_dir(root, "text.greet.polite")
    impl = (folder / "impl.py").read_text()
    assert 'GREETING = "hello"' in impl and 'PUNCT = ".,!?"' in impl
    assert "UNUSED" not in impl and "PATTERN" not in impl and "import re" not in impl
    (folder / "test_impl.py").write_text(
        "from impl import greet\n\n\n"
        "def test_greet():\n    assert greet('bob!') == 'hello, bob'\n\n\n"
        "def test_empty():\n    assert greet('') == 'hello, '\n"
    )
    assert pcat(root, "index").exit_code == 0
    result = pcat(root, "validate", "text.greet.polite")
    assert result.exit_code == 0, result.output


def test_add_fails_clearly_on_non_literal_module_name(root, tmp_path):
    source = tmp_path / "greeter.py"
    source.write_text(GREETER)
    result = pcat(root, "add", source, "--function", "squash", "--id", "text.squash.spaces")
    assert result.exit_code == 1
    assert "module-level name 'PATTERN'" in result.output and "not a literal" in result.output
    assert not pattern_dir(root, "text.squash.spaces").exists()


SORTER = textwrap.dedent(
    '''
    def sort_by_size(items, largest_first=False):
        """Sort items by absolute value."""
        return _ordered(items, reverse=largest_first, key=abs)


    def _ordered(items, key=None, reverse=False):
        return sorted(items, key=key, reverse=reverse)
    '''
).lstrip()


def test_render_renaming_helper_parameter_keeps_calls_working(root, tmp_path):
    source = tmp_path / "sorter.py"
    source.write_text(SORTER)
    assert pcat(root, "add", source, "--function", "sort_by_size", "--id", "sort.by_size.abs").exit_code == 0
    assert pcat(root, "index").exit_code == 0
    result = pcat(root, "render", "sort.by_size.abs", "--names", "f1.v2=descending", "f1.v1=by")
    assert result.exit_code == 0, result.output
    assert "return _ordered(items, descending=largest_first, by=abs)" in result.output
    namespace: dict = {}
    exec(result.output, namespace)  # noqa: S102 - test only
    assert namespace["sort_by_size"]([3, -5, 1], largest_first=True) == [-5, 3, 1]


def test_migrate_fingerprints_command(root):
    folder = pattern_dir(root, ITER)
    edit_yaml(folder, fingerprint="0" * 64)
    result = pcat(root, "migrate-fingerprints")
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0].split() == ["id", "old", "new", "status"]
    row = next(line for line in lines if line.startswith(f"{ITER}@v1"))
    assert row.split()[1] == "0" * 64 and row.split()[3] == "changed"
    assert sum("unchanged" in line for line in lines) == 5
    assert "1 of 6 fingerprint(s) changed; rules version 2" in result.output
    assert pcat(root, "validate", "--skip-tests").exit_code == 0


def test_migrate_fingerprints_command_reports_each_error(root):
    for pid in (ITER, "text.slugify.ascii"):
        (pattern_dir(root, pid) / "impl.py").write_text("X = make()\ndef f():\n    pass\n")
    result = pcat(root, "migrate-fingerprints")
    assert result.exit_code == 1
    errors = [line for line in result.output.splitlines() if line.startswith("error: ")]
    assert len(errors) == 3  # header + one line per broken pattern
