"""One page of a legacy SQLAlchemy ORM Query plus the total row count, as a tuple.

Requires: sqlalchemy>=1.4,<3. Uses the 1.x-style Query API (session.query(...)),
which SQLAlchemy 2.0 still supports but calls "legacy".
"""

from typing import Any

from sqlalchemy.orm import Query

MAX_PAGE_SIZE = 100


def paginate(query: Query, page: int = 1, page_size: int = 20) -> tuple[list[Any], int]:
    """Return (items on 1-based `page`, total rows) for `query`.

    `query` must have a deterministic order_by(), or pages may overlap or skip rows.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    total = query.order_by(None).count()  # Query.count() wraps the query in a subquery
    items = query.limit(page_size).offset((page - 1) * page_size).all()
    return items, total
