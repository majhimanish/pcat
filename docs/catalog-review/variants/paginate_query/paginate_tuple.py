"""One page of a SQLAlchemy 2.0 select plus the total row count, as a tuple.

Requires: sqlalchemy>=2.0,<3.
"""

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

MAX_PAGE_SIZE = 100


def paginate(
    session: Session, stmt: Select, page: int = 1, page_size: int = 20
) -> tuple[list[Any], int]:
    """Return (items on 1-based `page`, total rows) for `stmt`.

    `stmt` must have a deterministic ORDER BY, or pages may overlap or skip rows.
    Entity selects (select(User)) yield objects; column selects yield rows.
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
    return items, total
