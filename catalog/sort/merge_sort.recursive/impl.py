"""Top-down recursive merge sort returning a new list."""

from collections.abc import Sequence
from typing import Any


def merge_sort(items: Sequence[Any]) -> list[Any]:
    """Return a new list with `items` in ascending order (stable)."""
    if len(items) <= 1:
        return list(items)
    middle = len(items) // 2
    left = merge_sort(items[:middle])
    right = merge_sort(items[middle:])
    return _merge(left, right)


def _merge(left: list[Any], right: list[Any]) -> list[Any]:
    merged = []
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        # `<=` takes from the left run on ties, which keeps the sort stable.
        if left[i] <= right[j]:
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged
