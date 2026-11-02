from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def paginate_query(
    session: Session,
    query: Any,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Any], int]:
    """Return one page of results from a SQLAlchemy 2.0 ``Select`` along with
    the total number of rows the unpaginated query would return.

    Args:
        session: Active SQLAlchemy session.
        query: A ``select(...)`` statement (ordering should be set by the caller
            so pages are stable).
        page: 1-based page number.
        page_size: Number of items per page.

    Returns:
        A tuple of ``(items, total_count)``.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    # Count over the query as a subquery; drop ordering since it is irrelevant
    # to the count and can be expensive.
    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    if total == 0:
        return [], 0

    offset = (page - 1) * page_size
    page_stmt = query.limit(page_size).offset(offset)
    result = session.execute(page_stmt)

    # Single-entity selects yield scalars; multi-column selects yield Rows.
    if len(query.selected_columns) == 1 or _is_single_entity(query):
        items = list(result.scalars().all())
    else:
        items = list(result.all())

    return items, total


def _is_single_entity(query: Any) -> bool:
    """True if the select targets exactly one ORM entity."""
    try:
        descriptions = query.column_descriptions
    except AttributeError:
        return False
    return len(descriptions) == 1
