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
    The query should have a deterministic ORDER BY for stable pagination.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    offset = (page - 1) * page_size

    if hasattr(query, "statement"):
        # Legacy Query object
        total = query.order_by(None).count()
        items = query.limit(page_size).offset(offset).all()
    else:
        # 2.0-style Select
        count_stmt = select(func.count()).select_from(
            query.order_by(None).subquery()
        )
        total = session.execute(count_stmt).scalar_one()
        paged = query.limit(page_size).offset(offset)
        result = session.execute(paged)
        items = list(result.scalars().all()) if _is_single_entity(query) else list(result.all())

    return items, total


def _is_single_entity(stmt: Any) -> bool:
    """True if the Select returns a single column/entity per row."""
    return len(stmt.selected_columns) == 1 or len(stmt.column_descriptions) == 1
