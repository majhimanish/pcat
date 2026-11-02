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

    `query` may be a SQLAlchemy 2.0 `Select` statement or a legacy `Query`
    object. The query should have a deterministic ORDER BY for stable paging.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    offset = (page - 1) * page_size

    if hasattr(query, "statement"):  # legacy Query object
        stmt = query.statement
    else:
        stmt = query

    # Count over a subquery so joins, filters, DISTINCT and GROUP BY are respected.
    count_stmt = select(func.count()).select_from(
        stmt.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    page_stmt = stmt.limit(page_size).offset(offset)

    if hasattr(query, "statement"):
        items = list(query.limit(page_size).offset(offset).all())
    else:
        result = session.execute(page_stmt)
        # Single-entity selects yield ORM objects; otherwise return Row objects.
        if len(stmt.column_descriptions) == 1:
            items = list(result.scalars().all())
        else:
            items = list(result.all())

    return items, total
