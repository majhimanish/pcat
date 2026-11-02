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

    `query` may be a legacy `Query` object or a 2.0-style `Select` statement.
    Add a deterministic ORDER BY to the query for stable pagination.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    offset = (page - 1) * page_size

    # Legacy Query object (session.query(...))
    if hasattr(query, "limit") and hasattr(query, "count") and not hasattr(query, "subquery_"):
        if hasattr(query, "order_by") and hasattr(query, "session"):
            total = query.order_by(None).count()
            items = query.limit(page_size).offset(offset).all()
            return items, total

    # 2.0-style Select statement
    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    page_stmt = query.limit(page_size).offset(offset)
    result = session.execute(page_stmt)

    # Return ORM entities when the select targets a single entity,
    # otherwise return Row objects.
    if len(query.column_descriptions) == 1:
        items = result.scalars().all()
    else:
        items = result.all()

    return items, total
