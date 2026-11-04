"""One page of a SQLAlchemy 2.0 select with page metadata, as a dict.

Requires: sqlalchemy>=2.0,<3.
"""

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

MAX_PAGE_SIZE = 100


def paginate(session: Session, stmt: Select, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    """Return {"items", "total", "page", "page_size", "pages"} for 1-based `page`.

    `stmt` must have a deterministic ORDER BY, or pages may overlap or skip rows.
    A page past the end returns no items (not an error), with the real totals.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = session.execute(count_stmt).scalar_one()
    result = session.execute(stmt.limit(page_size).offset((page - 1) * page_size))
    single_entity = len(stmt.column_descriptions) == 1
    items = list(result.scalars()) if single_entity else list(result)
    pages = (total + page_size - 1) // page_size
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}
