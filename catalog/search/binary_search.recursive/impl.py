"""Recursive binary search over an ascending sequence (no slicing, O(log n) depth)."""

from collections.abc import Sequence
from typing import Any


def binary_search(items: Sequence[Any], target: Any) -> int:
    """Return an index of `target` in ascending `items`, or -1 if absent."""
    return _search(items, target, 0, len(items) - 1)


def _search(items: Sequence[Any], target: Any, low: int, high: int) -> int:
    if low > high:
        return -1
    mid = low + (high - low) // 2
    value = items[mid]
    if value == target:
        return mid
    if value < target:
        return _search(items, target, mid + 1, high)
    return _search(items, target, low, mid - 1)
