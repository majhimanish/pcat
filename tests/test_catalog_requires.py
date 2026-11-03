"""`requires` metadata (v2.2): schema, index and the pyproject `catalog` extra."""

from __future__ import annotations

import json
import re
import tomllib

import pytest

from conftest import REPO_ROOT, edit_yaml, pattern_dir
from pcat import canonical
from pcat import catalog as cat

ITER = "search.binary_search.iterative"


def test_requires_defaults_to_empty_and_is_empty_in_index(root):
    # v3 made every metadata key present in every index entry (was: absent when empty).
    entries = json.loads((root / "catalog" / "index.json").read_text())["patterns"]
    seeds = [e for e in entries if e["id"] == ITER]
    assert seeds and seeds[0]["requires"] == []
    assert cat.get_one(root, ITER).meta.requires == []


def test_requires_is_indexed_sorted_and_does_not_change_fingerprint(root):
    before = cat.analyze_pattern(cat.get_one(root, ITER)).fingerprint
    edit_yaml(pattern_dir(root, ITER), requires=["sortedcontainers>=2.4,<3", "Attrs>=23"])
    cat.write_index(root)
    pattern = cat.get_one(root, ITER)
    assert cat.analyze_pattern(pattern).fingerprint == before == pattern.meta.fingerprint
    entry = next(e for e in json.loads((root / "catalog" / "index.json").read_text())["patterns"]
                 if e["id"] == ITER)
    assert entry["requires"] == ["Attrs>=23", "sortedcontainers>=2.4,<3"]
    assert cat.validate(root, run_tests=False) == []


@pytest.mark.parametrize("bad", [["not a requirement!"], ["pkg>=1", "PKG<2"], ["https://x/y.whl"], "pkg"])
def test_invalid_requires_rejected(root, bad):
    edit_yaml(pattern_dir(root, ITER), requires=bad)
    problems = cat.validate(root, run_tests=False)
    assert any(p.check == "1" and "requires" in p.message for p in problems)


def test_pyproject_catalog_extra_covers_every_pattern_requirement():
    extra = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())["project"][
        "optional-dependencies"]["catalog"]
    available = {re.match(r"[A-Za-z0-9._-]+", r).group(0).lower(): r for r in extra}
    for pattern in cat.load_catalog(REPO_ROOT):
        for req in pattern.meta.requires:
            name = re.match(r"[A-Za-z0-9._-]+", req).group(0).lower()
            assert available.get(name) == req, f"{pattern.label}: add {req!r} to the catalog extra"


def test_requires_never_enters_canonical_text():
    pattern = cat.get_one(REPO_ROOT, ITER)
    assert "requires" not in cat.analyze_pattern(pattern).text and canonical.CANONICAL_VERSION == 2
