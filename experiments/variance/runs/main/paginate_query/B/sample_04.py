from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select


def get_total_count(session: Session, query: Select) -> int:
    """Return the total number of rows the query would produce, ignoring any LIMIT/OFFSET/ORDER BY."""
    count_query = select(func.count()).select_from(
        query.order_by(None).limit(None).offset(None).subquery()
    )
    return session.execute(count_query).scalar_one()


def get_page(
    session: Session,
    query: Select,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Any], int]:
    """
    Fetch page `page` (1-indexed) of `query` with `page_size` rows per page.

    Returns a tuple of (rows, total_count), where total_count is the overall
    number of rows matching the query across all pages.

    Note: the query should have a deterministic ORDER BY for stable pagination.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    total = get_total_count(session, query)

    paged_query = query.limit(page_size).offset((page - 1) * page_size)
    result = session.execute(paged_query)

    # For ORM entity queries (select(Model)), return entities; otherwise return Row objects.
    if len(query.column_descriptions) == 1 and query.column_descriptions[0].get("entity") is not None \
            and query.column_descriptions[0].get("expr") is query.column_descriptions[0].get("entity"):
        rows = list(result.scalars().all())
    else:
        rows = list(result.all())

    return rows, total
