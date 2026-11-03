"""The committed seed catalog itself must stay valid and round-trip."""

from __future__ import annotations

import pytest

from conftest import REPO_ROOT, SEED_IDS
from pcat import canonical
from pcat import catalog as cat

# Fingerprints recorded in v1; they must never change (CLAUDE.md invariants 1 and 2).
SEED_FINGERPRINTS = {
    "collections.group_by.dict_of_lists": "68a881fa849c71ad539062fde96eb18497ec0f064acc007636aded7f84c6e441",
    "retry.with_exponential_backoff": "ba244d247458e8dfb0e5c79174e368ffb70b83553a5487743925d398b9c3c0de",
    "search.binary_search.iterative": "67f21b9d7bc1f6a3b2cd0ab253d49a40537e6e9f197ae6524bf874c62bb3488c",
    "search.binary_search.recursive": "f19b87a5616bf85332fe97ca1057a3c00bb7fe3f3a31200ffe3f7437505ddd7c",
    "sort.merge_sort.recursive": "cf06bfe1351b06a8bf0def374666a64d11a3439a90dc5cc99d3e53adc8458576",
    "text.slugify.ascii": "3a2864bbf5feb3ef52129e3db1e8a4f1ec123d6ce0e99c9ae5cebd7c1f83a5ec",
}


def test_real_catalog_validates_including_pattern_tests():
    problems = cat.validate(REPO_ROOT)
    assert problems == [], "\n".join(map(str, problems))


def test_catalog_contains_all_seeds_unchanged():
    # v2.2 added application patterns; the 6 seeds stay, with their original fingerprints.
    patterns = {p.meta.id: p for p in cat.load_catalog(REPO_ROOT)}
    assert set(SEED_IDS) <= set(patterns)
    assert {pid: patterns[pid].meta.fingerprint for pid in SEED_IDS} == SEED_FINGERPRINTS


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
