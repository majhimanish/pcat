from collections.abc import Sequence
from typing import Any


def sum_large(rows):
    # same shape as total_price, but different literal values
    value = 0
    for row in rows:
        if row.price > 50:
            value += row.price * 3
    return value


def find_index(seq: Sequence[Any], wanted: Any) -> int:
    # copy of the catalog's binary_search (iterative) with other names
    low = 0
    high = len(seq) - 1
    while low <= high:
        mid = low + (high - low) // 2
        value = seq[mid]
        if value == wanted:
            return mid
        if value < wanted:
            low = mid + 1
        else:
            high = mid - 1
    return -1


def find_index_or_minus_two(seq: Sequence[Any], wanted: Any) -> int:
    # same as above with a different literal: near-covered, not covered
    low = 0
    high = len(seq) - 1
    while low <= high:
        mid = low + (high - low) // 2
        value = seq[mid]
        if value == wanted:
            return mid
        if value < wanted:
            low = mid + 1
        else:
            high = mid - 1
    return -2
