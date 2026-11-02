from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session
from sqlalchemy.sql import Select


def paginate_query(
    session: Session,
    query: Query | Select,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Any], int]:
    """Return (items, total_count) for one page of a SQLAlchemy query.

    `page` is 1-indexed. `query` may be a legacy ``Query`` or a 2.0-style
    ``Select``. The query should have a deterministic ORDER BY for stable pages.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    offset = (page - 1) * page_size

    if isinstance(query, Query):
        # Drop ordering for the count; it is irrelevant and can be slow.
        total = query.order_by(None).count()
        items = query.limit(page_size).offset(offset).all()
        return items, total

    # 2.0-style Select: count over a subquery so joins, DISTINCT and
    # GROUP BY are counted correctly.
    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    page_stmt = query.limit(page_size).offset(offset)
    result = session.execute(page_stmt)
    # Single-entity selects yield scalars; multi-column selects yield rows.
    if len(query.selected_columns) == 1:
        items = list(result.scalars().all())
    else:
        items = list(result.all())
    return items, total
