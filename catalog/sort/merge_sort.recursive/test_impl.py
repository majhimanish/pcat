import random

import pytest

from impl import merge_sort


@pytest.mark.parametrize(
    "items",
    [
        [3, 1, 2],
        [5, 4, 3, 2, 1],
        [1, 2, 3, 4, 5],
        [2, 2, 1, 1, 3, 3],
        [-1, 0, -5, 10, 7],
        ["pear", "apple", "fig"],
        [1.5, -0.5, 1.0],
    ],
)
def test_matches_sorted(items):
    assert merge_sort(items) == sorted(items)


def test_empty_input():
    assert merge_sort([]) == []


def test_single_element():
    assert merge_sort([42]) == [42]


def test_input_not_modified_and_new_list_returned():
    items = [3, 1, 2]
    result = merge_sort(items)
    assert items == [3, 1, 2]
    assert result is not items
    single = [1]
    assert merge_sort(single) is not single


def test_accepts_tuples():
    assert merge_sort((3, 1, 2)) == [1, 2, 3]


class Card:
    def __init__(self, rank, label):
        self.rank = rank
        self.label = label

    def __le__(self, other):
        return self.rank <= other.rank


def test_stable_for_equal_keys():
    cards = [Card(2, "a"), Card(1, "b"), Card(2, "c"), Card(1, "d")]
    assert [c.label for c in merge_sort(cards)] == ["b", "d", "a", "c"]


def test_random_inputs():
    rng = random.Random(1234)
    for size in range(50):
        items = [rng.randint(-20, 20) for _ in range(size)]
        assert merge_sort(items) == sorted(items)
