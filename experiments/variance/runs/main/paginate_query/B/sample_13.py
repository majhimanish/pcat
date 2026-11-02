from math import ceil
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Query


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def paginate(
    query: Query,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_page_size: int = MAX_PAGE_SIZE,
) -> tuple[list[Any], int]:
    """Return (items_for_page, total_count) for a SQLAlchemy ORM query.

    - page is 1-indexed; values < 1 are clamped to 1.
    - page_size is clamped to the range [1, max_page_size].
    - total_count is the number of rows the unpaginated query would return,
      computed via a subquery so it stays correct with joins, filters,
      DISTINCT and GROUP BY.
    - Any existing ORDER BY is preserved for the page query, so results are
      stable; callers should always order by a unique column for deterministic
      paging.
    """
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), max_page_size))

    # Count over the query as a subquery; strip ordering since it is irrelevant
    # to the count and can be expensive.
    count_stmt = select(func.count()).select_from(
        query.order_by(None).limit(None).offset(None).subquery()
    )
    total = query.session.execute(count_stmt).scalar_one()

    items = query.limit(page_size).offset((page - 1) * page_size).all()
    return items, total


def total_pages(total: int, page_size: int = DEFAULT_PAGE_SIZE) -> int:
    """Number of pages needed for `total` rows at `page_size` per page."""
    page_size = max(1, int(page_size))
    return ceil(total / page_size) if total else 0
