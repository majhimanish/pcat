from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def paginate_query(
    session: Session,
    query: Any,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Any], int]:
    """Return (items, total_count) for the requested 1-based page of a query.

    `query` may be a 2.0-style Select statement or a legacy Query object.
    The total reflects the number of rows the query would return without
    pagination (ordering is dropped from the count for efficiency).
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    # Support legacy Query objects by extracting the underlying statement.
    stmt = query.statement if hasattr(query, "statement") else query

    count_stmt = select(func.count()).select_from(
        stmt.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    if total == 0:
        return [], 0

    offset = (page - 1) * page_size
    page_stmt = stmt.limit(page_size).offset(offset)

    result = session.execute(page_stmt)
    # Return ORM entities if the select has a single entity, else Row objects.
    if len(stmt.column_descriptions) == 1 if hasattr(stmt, "column_descriptions") else False:
        items = list(result.scalars().all())
    else:
        items = list(result.all())

    return items, total
