from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def paginate_query(
    session: Session,
    query: Any,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Any], int]:
    """Return one page of results and the total number of matching rows.

    Args:
        session: The active SQLAlchemy session.
        query: A SQLAlchemy 2.0 ``Select`` statement (e.g. ``select(User)``).
            It should have a deterministic ``order_by`` for stable paging.
        page: 1-based page number.
        per_page: Number of items per page.

    Returns:
        A tuple of ``(items, total)`` where ``items`` is the list of results
        for the requested page and ``total`` is the count of all rows the
        query would return without pagination.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if per_page < 1:
        raise ValueError("per_page must be >= 1")

    # Count over a subquery so joins, filters, DISTINCT and GROUP BY are
    # respected. Ordering is irrelevant for counting, so drop it.
    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    if total == 0:
        return [], 0

    page_stmt = query.limit(per_page).offset((page - 1) * per_page)
    items = session.execute(page_stmt).scalars().all()

    return list(items), total
