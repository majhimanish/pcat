from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select


def paginate_query(
    session: Session,
    query: Select,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Any], int]:
    """Return one page of results from a SQLAlchemy 2.0-style select, plus the total count.

    Args:
        session: Active SQLAlchemy session.
        query: A ``select()`` statement. It should have a deterministic
            ORDER BY for stable pagination.
        page: 1-based page number.
        page_size: Number of rows per page.

    Returns:
        A tuple ``(items, total)`` where ``items`` is the list of rows for the
        requested page and ``total`` is the number of rows the unpaginated
        query would return.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    # Count over the original query as a subquery (ordering is irrelevant for counting).
    count_stmt = select(func.count()).select_from(query.order_by(None).subquery())
    total = session.execute(count_stmt).scalar_one()

    offset = (page - 1) * page_size
    page_stmt = query.limit(page_size).offset(offset)
    result = session.execute(page_stmt)

    # scalars() for single-entity selects; fall back to full rows otherwise.
    if len(query.selected_columns) == 1 or _is_single_entity(query):
        items = list(result.scalars().all())
    else:
        items = list(result.all())

    return items, total


def _is_single_entity(query: Select) -> bool:
    """True if the select targets exactly one ORM entity (e.g. ``select(User)``)."""
    descriptions = query.column_descriptions
    return len(descriptions) == 1 and descriptions[0].get("entity") is not None
