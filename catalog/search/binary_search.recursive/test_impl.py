import pytest

from impl import binary_search


@pytest.mark.parametrize("target,index", [(1, 0), (3, 1), (5, 2), (7, 3), (9, 4)])
def test_finds_every_element(target, index):
    assert binary_search([1, 3, 5, 7, 9], target) == index


@pytest.mark.parametrize("target", [0, 2, 4, 8, 10])
def test_missing_returns_minus_one(target):
    assert binary_search([1, 3, 5, 7, 9], target) == -1


def test_empty_input():
    assert binary_search([], 1) == -1


def test_single_element():
    assert binary_search([4], 4) == 0
    assert binary_search([4], 5) == -1


def test_duplicates_return_any_matching_index():
    items = [1, 2, 2, 2, 3]
    assert items[binary_search(items, 2)] == 2


def test_recursion_depth_is_logarithmic():
    # 1,000,000 elements need ~20 levels; far below the default recursion limit.
    items = range(1_000_000)
    assert binary_search(items, 999_999) == 999_999
    assert binary_search(items, -5) == -1
