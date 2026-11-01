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


def test_works_on_tuples_and_strings():
    assert binary_search(("a", "b", "c"), "c") == 2


def test_large_input():
    items = list(range(0, 200_000, 2))
    assert binary_search(items, 123_456) == 61_728
    assert binary_search(items, 123_457) == -1
