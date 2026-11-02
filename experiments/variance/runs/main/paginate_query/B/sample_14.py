from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select


def paginate(
    session: Session,
    query: Select,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Any], int]:
    """Return (rows_for_page, total_row_count) for a SQLAlchemy 2.0 select().

    `page` is 1-based. The query should have a deterministic ORDER BY so
    pages are stable. Rows are Row objects; use `.scalars()` semantics via
    `paginate_scalars` if the query selects a single ORM entity.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    # Count over the query as a subquery (works with joins, group by, distinct).
    # Ordering is irrelevant to the count, so drop it for efficiency.
    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    offset = (page - 1) * page_size
    rows = session.execute(query.limit(page_size).offset(offset)).all()
    return rows, total


def paginate_scalars(
    session: Session,
    query: Select,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Any], int]:
    """Like `paginate`, but returns scalar values / ORM entities (first column).

    Note: with joined eager loading of collections, call `.unique()` yourself
    or use selectinload to avoid row-multiplication affecting the limit.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    offset = (page - 1) * page_size
    items = session.scalars(query.limit(page_size).offset(offset)).all()
    return list(items), total
