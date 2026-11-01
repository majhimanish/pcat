"""Iterative binary search over an ascending sequence."""

from collections.abc import Sequence
from typing import Any


def binary_search(items: Sequence[Any], target: Any) -> int:
    """Return an index of `target` in ascending `items`, or -1 if absent."""
    low = 0
    high = len(items) - 1
    while low <= high:
        # low + (high - low) // 2 never exceeds high, even with fixed-width ints.
        mid = low + (high - low) // 2
        value = items[mid]
        if value == target:
            return mid
        if value < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
