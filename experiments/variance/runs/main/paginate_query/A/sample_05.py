from typing import Any, List, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session


def paginate_query(
    session: Session,
    query: Query,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Any], int]:
    """Return (items, total_count) for one page of a SQLAlchemy ORM query.

    `page` is 1-based. The total count reflects the full, unpaginated query.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    # Count over a subquery so joins, filters, and DISTINCT are respected.
    # order_by is dropped from the count since it doesn't affect the total.
    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    if total == 0:
        return [], 0

    items = (
        query.limit(page_size)
        .offset((page - 1) * page_size)
        .all()
    )
    return items, total
