from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session


def paginate_query(
    session: Session,
    query: Query | Any,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Any], int]:
    """Return (items, total) for the requested 1-based page of a query.

    Accepts either a legacy ``Query`` or a 2.0-style ``Select`` statement.
    The total is the number of rows the query would return without
    pagination (ordering is dropped for the count to keep it cheap).
    Add an ``order_by`` to the query for deterministic pages.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if per_page < 1:
        raise ValueError("per_page must be >= 1")

    offset = (page - 1) * per_page

    if isinstance(query, Query):
        total = query.order_by(None).count()
        items = query.limit(per_page).offset(offset).all()
        return items, total

    # 2.0-style Select statement
    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()
    items = list(
        session.execute(query.limit(per_page).offset(offset)).scalars().all()
    )
    return items, total
