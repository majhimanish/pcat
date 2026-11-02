from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session


def paginate_query(
    session: Session,
    query: Query | Any,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Any], int]:
    """Return (items, total_count) for one page of a SQLAlchemy query.

    Accepts either a legacy ``Query`` or a 2.0-style ``Select`` statement.
    ``page`` is 1-indexed. The query should have a deterministic ORDER BY
    for stable pagination.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if per_page < 1:
        raise ValueError("per_page must be >= 1")

    offset = (page - 1) * per_page

    if isinstance(query, Query):
        # Strip ordering for the count query; it is irrelevant and slower.
        total = query.order_by(None).count()
        items = query.limit(per_page).offset(offset).all()
        return items, total

    # 2.0-style Select
    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()
    items = list(session.scalars(query.limit(per_page).offset(offset)).all())
    return items, total
