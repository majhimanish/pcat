from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def paginate_query(
    session: Session,
    query: Any,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Any], int]:
    """Return (items, total) for one page of a SQLAlchemy 2.0 Select.

    - `page` is 1-indexed; values below 1 are treated as 1.
    - `per_page` must be a positive integer.
    - `total` is the count of all rows matching the query, ignoring
      pagination.
    - If the query has no ORDER BY, results may be inconsistent across
      pages; supply a deterministic ordering for stable pagination.
    """
    if per_page < 1:
        raise ValueError("per_page must be a positive integer")
    page = max(1, page)

    # Count over the query as a subquery so joins, filters, DISTINCT and
    # GROUP BY are all respected. Ordering is dropped as it is irrelevant
    # to the count.
    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    if total == 0:
        return [], 0

    page_stmt = query.limit(per_page).offset((page - 1) * per_page)
    result = session.execute(page_stmt)

    # Single-entity selects yield scalars (model instances); multi-column
    # selects yield Row objects.
    if len(query.selected_columns) == 1 or _is_single_entity(query):
        items = list(result.scalars().all())
    else:
        items = list(result.all())

    return items, total


def _is_single_entity(query: Any) -> bool:
    """True if the select targets exactly one ORM entity."""
    descriptions = query.column_descriptions
    return len(descriptions) == 1
