from typing import Any, List, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session


def paginate_query(
    session: Session,
    query: Query,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Any], int]:
    """Return (items, total_count) for the requested 1-based page of `query`.

    The query should have a deterministic ORDER BY for stable pagination.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    # Count over the query as a subquery, without ordering, so joins,
    # filters, and DISTINCT/GROUP BY are all respected.
    count_stmt = select(func.count()).select_from(
        query.order_by(None).limit(None).offset(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    if total == 0:
        return [], 0

    items = query.limit(page_size).offset((page - 1) * page_size).all()
    return items, total
