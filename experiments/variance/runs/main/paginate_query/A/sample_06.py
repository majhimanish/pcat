from typing import Any, List, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def paginate_query(
    session: Session,
    query: Any,
    page: int = 1,
    per_page: int = 20,
) -> Tuple[List[Any], int]:
    """Return (items, total) for one page of a SQLAlchemy 2.x select() or legacy Query.

    `page` is 1-indexed. `total` is the count of all rows matching the query
    before pagination. The query should already include any ordering so that
    pages are stable.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if per_page < 1:
        raise ValueError("per_page must be >= 1")

    offset = (page - 1) * per_page

    # Legacy Query object (session.query(...))
    if hasattr(query, "limit") and hasattr(query, "count") and not hasattr(query, "subquery_"):
        total = query.order_by(None).count()
        items = query.limit(per_page).offset(offset).all()
        return items, total

    # SQLAlchemy 2.x Select construct
    count_stmt = select(func.count()).select_from(query.order_by(None).subquery())
    total = session.execute(count_stmt).scalar_one()

    page_stmt = query.limit(per_page).offset(offset)
    result = session.execute(page_stmt)
    items = result.scalars().all() if _returns_single_entity(query) else result.all()
    return items, total


def _returns_single_entity(stmt: Any) -> bool:
    """True if the select() has exactly one column/entity, so scalars() is appropriate."""
    try:
        return len(stmt.selected_columns) == 1 or len(stmt.column_descriptions) == 1
    except AttributeError:
        return False
