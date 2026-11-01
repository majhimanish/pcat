"""Group an iterable into a dict of lists keyed by a function."""

from collections.abc import Callable, Hashable, Iterable
from typing import Any


def group_by(items: Iterable[Any], key: Callable[[Any], Hashable]) -> dict[Hashable, list[Any]]:
    """Map key(item) -> items with that key.

    Keys appear in the order they are first seen, and items keep their input
    order within each group. Unlike itertools.groupby, input need not be sorted.
    """
    groups: dict[Hashable, list[Any]] = {}
    for item in items:
        groups.setdefault(key(item), []).append(item)
    return groups
