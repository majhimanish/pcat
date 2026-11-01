"""The committed seed catalog itself must stay valid and round-trip."""

from __future__ import annotations

import pytest

from conftest import REPO_ROOT, SEED_IDS
from pcat import canonical
from pcat import catalog as cat


def test_real_catalog_validates_including_pattern_tests():
    problems = cat.validate(REPO_ROOT)
    assert problems == [], "\n".join(map(str, problems))


def test_catalog_contains_exactly_the_seeds():
    assert sorted(p.meta.id for p in cat.load_catalog(REPO_ROOT)) == SEED_IDS


@pytest.mark.parametrize("pattern_id", SEED_IDS)
def test_render_round_trips(pattern_id):
    pattern = cat.get_one(REPO_ROOT, pattern_id)
    result = cat.analyze_pattern(pattern)
    rendered = canonical.render(result.text, result.name_map)
    assert canonical.canonicalize(rendered, pattern.meta.entry_point) == result.text
    assert canonical.extract_name_map(rendered, pattern.meta.entry_point) == result.name_map
    assert result.fingerprint == pattern.meta.fingerprint
