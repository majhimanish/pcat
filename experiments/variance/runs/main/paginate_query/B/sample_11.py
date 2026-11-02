from typing import Any, List, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session


def paginate(
    query: Query,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Any], int]:
    """Return (items_on_page, total_count) for a legacy ORM Query.

    page is 1-based. Raises ValueError for invalid page or page_size.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    # Count over a subquery so DISTINCT, GROUP BY, and joins are counted correctly.
    # order_by is dropped from the count since it does not affect the total.
    total = query.order_by(None).count()

    items = query.limit(page_size).offset((page - 1) * page_size).all()
    return items, total


def paginate_select(
    session: Session,
    stmt: Any,
    page: int = 1,
    page_size: int = 20,
    scalars: bool = True,
) -> Tuple[List[Any], int]:
    """Return (items_on_page, total_count) for a 2.0-style select() statement.

    page is 1-based. If scalars is True, returns the first column/entity of
    each row (typical for select(Model)); otherwise returns Row objects.
    Raises ValueError for invalid page or page_size.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    count_stmt = select(func.count()).select_from(
        stmt.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    page_stmt = stmt.limit(page_size).offset((page - 1) * page_size)
    result = session.execute(page_stmt)
    items = result.scalars().all() if scalars else result.all()
    return items, total
