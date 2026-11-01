from impl import group_by


def test_groups_by_key():
    words = ["apple", "avocado", "banana", "blueberry", "cherry"]
    assert group_by(words, lambda w: w[0]) == {
        "a": ["apple", "avocado"],
        "b": ["banana", "blueberry"],
        "c": ["cherry"],
    }


def test_unsorted_input_and_first_seen_key_order():
    result = group_by([1, 2, 3, 4, 5, 6], lambda n: n % 3)
    assert result == {1: [1, 4], 2: [2, 5], 0: [3, 6]}
    assert list(result) == [1, 2, 0]


def test_item_order_preserved_within_group():
    pairs = [("x", 3), ("y", 1), ("x", 1), ("x", 2)]
    assert group_by(pairs, lambda p: p[0])["x"] == [("x", 3), ("x", 1), ("x", 2)]


def test_empty_input():
    assert group_by([], lambda x: x) == {}


def test_accepts_generators_and_single_group():
    assert group_by((n for n in range(3)), lambda n: "all") == {"all": [0, 1, 2]}


def test_none_is_a_valid_key():
    assert group_by([None, 1, None], lambda x: x) == {None: [None, None], 1: [1]}
