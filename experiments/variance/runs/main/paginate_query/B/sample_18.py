from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Query


def paginate(query: Query, page: int = 1, per_page: int = 20) -> tuple[list[Any], int]:
    """Return (items, total) for the requested 1-indexed page of a SQLAlchemy query.

    The query should have a deterministic ORDER BY so pages are stable.
    `total` is the number of rows the unpaginated query would return.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if per_page < 1:
        raise ValueError("per_page must be >= 1")

    # Count over a subquery so joins, filters, DISTINCT and GROUP BY are
    # counted correctly. Ordering is dropped since it doesn't affect the count.
    total = query.session.execute(
        select(func.count()).select_from(query.order_by(None).subquery())
    ).scalar_one()

    items = query.limit(per_page).offset((page - 1) * per_page).all()

    return items, total
