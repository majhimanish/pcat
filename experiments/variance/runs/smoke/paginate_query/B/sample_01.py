from typing import Any, List, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session


def paginate(
    query: Any,
    page: int,
    page_size: int,
    session: Session | None = None,
) -> Tuple[List[Any], int]:
    """Return (items_on_page, total_count) for a SQLAlchemy query.

    Works with both legacy ``Query`` objects and 2.0-style ``Select``
    statements. Pages are 1-indexed. For ``Select`` statements, a
    ``session`` is required.
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

    if session is None:
        raise ValueError("session is required when paginating a Select statement")

    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    page_stmt = query.limit(page_size).offset(offset)
    result = session.execute(page_stmt)
    # Single-entity selects return scalars; multi-column selects return rows.
    if len(query.selected_columns) == 1:
        items = list(result.scalars().all())
    else:
        items = list(result.all())

    return items, total
