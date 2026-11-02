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


def _load_impl(pattern):
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"impl_{pattern.meta.id}", pattern.impl_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, pattern.meta.entry_point)


SAMPLE_CALLS = {
    "collections.group_by.dict_of_lists": [((["ab", "ac", "b"], lambda s: s[0]), {}), (([], len), {})],
    "retry.with_exponential_backoff": [((lambda: 7,), {}), ((lambda: None,), {})],
    "search.binary_search.iterative": [(([1, 3, 5], 5), {}), (([], 1), {}), (([1, 3], 2), {})],
    "search.binary_search.recursive": [(([1, 3, 5], 5), {}), (([], 1), {}), (([1, 3], 2), {})],
    "sort.merge_sort.recursive": [(([3, 1, 2, 1],), {}), (([],), {})],
    "text.slugify.ascii": [(("Hello Wörld!",), {}), (("",), {})],
}


@pytest.mark.parametrize("pattern_id", SEED_IDS)
def test_canonical_text_is_runnable_and_behaves_like_impl(pattern_id):
    pattern = cat.get_one(REPO_ROOT, pattern_id)
    text = cat.analyze_pattern(pattern).text
    namespace: dict = {}
    exec(compile(text, f"<canonical {pattern_id}>", "exec"), namespace)  # noqa: S102
    original = _load_impl(pattern)
    for args, kwargs in SAMPLE_CALLS[pattern_id]:
        assert namespace["f0"](*args, **kwargs) == original(*args, **kwargs)
