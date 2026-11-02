from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session


def paginate_query(
    session: Session,
    query: Query | Any,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Any], int]:
    """Return (items, total_count) for the requested 1-based page.

    Accepts either a legacy ``Query`` or a 2.0-style ``Select`` statement.
    The query should have a deterministic ORDER BY for stable pagination.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    offset = (page - 1) * page_size

    if isinstance(query, Query):
        total = query.order_by(None).count()
        items = query.limit(page_size).offset(offset).all()
        return items, total

    # 2.0-style Select
    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()
    rows = session.execute(query.limit(page_size).offset(offset))
    items = list(rows.scalars().all()) if _returns_single_entity(query) else list(rows.all())
    return items, total


def _returns_single_entity(stmt: Any) -> bool:
    """True if the select has exactly one column/entity (so scalars() is appropriate)."""
    return len(stmt.selected_columns) == 1 or len(stmt.column_descriptions) == 1
