from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session


def paginate_query(
    session: Session,
    query: Query | Any,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Any], int]:
    """Return (items, total_count) for the requested 1-based page.

    `query` may be a legacy `Query` object or a 2.0-style `Select` statement.
    The query should have a deterministic ORDER BY for stable pagination.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if per_page < 1:
        raise ValueError("per_page must be >= 1")

    offset = (page - 1) * per_page

    if isinstance(query, Query):
        # Legacy Query API: drop ordering for the count to keep it cheap.
        total = query.order_by(None).count()
        items = query.limit(per_page).offset(offset).all()
        return items, total

    # 2.0-style Select statement
    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    page_stmt = query.limit(per_page).offset(offset)
    result = session.execute(page_stmt)

    # Return ORM entities when the select targets a single entity,
    # otherwise return Row objects.
    if len(query.column_descriptions) == 1:
        items = list(result.scalars().all())
    else:
        items = list(result.all())

    return items, total
