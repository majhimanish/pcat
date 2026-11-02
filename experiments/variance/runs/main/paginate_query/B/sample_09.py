from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select


def paginate(
    session: Session,
    query: Select,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Any], int]:
    """Return (rows for the requested page, total row count).

    `query` is a SQLAlchemy 2.0 select() statement. It should have a
    deterministic ORDER BY so pages are stable. Pages are 1-indexed.
    Rows are returned as Row objects; for single-entity selects, use
    `session.scalars(...)` semantics by calling `.scalars()` instead
    (see `paginate_scalars`).
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    # Count over the query as a subquery, dropping ORDER BY for efficiency.
    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    page_stmt = query.limit(page_size).offset((page - 1) * page_size)
    rows = list(session.execute(page_stmt).all())
    return rows, total


def paginate_scalars(
    session: Session,
    query: Select,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Any], int]:
    """Like `paginate`, but returns first-column scalars (e.g. ORM entities
    for `select(Model)`) instead of Row objects."""
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    page_stmt = query.limit(page_size).offset((page - 1) * page_size)
    items = list(session.scalars(page_stmt).all())
    return items, total
