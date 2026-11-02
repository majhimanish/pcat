from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def paginate_query(
    session: Session,
    query: Any,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Any], int]:
    """Return (items, total_count) for one page of a SQLAlchemy query.

    `query` may be a 2.0-style Select statement or a legacy Query object.
    `page` is 1-indexed. The query should have a deterministic ORDER BY
    for stable pagination.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    offset = (page - 1) * page_size

    # Legacy Query object support
    if hasattr(query, "statement") and hasattr(query, "session"):
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

    # Single-entity selects return scalars; multi-column selects return rows
    if len(query.selected_columns) == 1 or _is_single_entity(query):
        items = list(result.scalars().all())
    else:
        items = list(result.all())

    return items, total


def _is_single_entity(query: Any) -> bool:
    """True if the Select targets exactly one ORM entity."""
    try:
        descriptions = query.column_descriptions
    except AttributeError:
        return False
    return len(descriptions) == 1
