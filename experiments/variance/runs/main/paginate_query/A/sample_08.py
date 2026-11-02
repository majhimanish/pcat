from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def paginate_query(
    session: Session,
    query: Any,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Any], int]:
    """Return (items, total) for one page of a SQLAlchemy 2.0-style select().

    - page is 1-indexed.
    - total is the count of all rows matching the query, ignoring pagination.
    - Any existing ORDER BY is dropped for the count query (cheaper), but kept
      for the page query. Add an ORDER BY to `query` for deterministic pages.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if per_page < 1:
        raise ValueError("per_page must be >= 1")

    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    offset = (page - 1) * per_page
    page_stmt = query.limit(per_page).offset(offset)

    result = session.execute(page_stmt)
    # Single-entity selects return model instances; multi-column selects
    # return Row objects.
    first_col_is_entity = len(page_stmt.column_descriptions) == 1 and bool(
        page_stmt.column_descriptions[0].get("entity")
    ) and page_stmt.column_descriptions[0].get("expr") is page_stmt.column_descriptions[0].get("entity")
    items = result.scalars().all() if first_col_is_entity else result.all()

    return items, total
