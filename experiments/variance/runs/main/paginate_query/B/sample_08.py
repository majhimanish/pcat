from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Query


def paginate(
    query: Any,
    page: int = 1,
    per_page: int = 20,
    max_per_page: int = 100,
) -> tuple[list[Any], int]:
    """Return (items, total) for one page of a SQLAlchemy query.

    Accepts a legacy ``Query`` (ORM session query) or a 2.0-style ``Select``
    (in which case the query must be bound to a session via the ``session``
    attribute is NOT available, so pass a Query for Select-less use; for
    Select, use ``paginate_select`` below).

    ``page`` is 1-indexed. Invalid values are clamped: page < 1 becomes 1,
    per_page is limited to the range [1, max_per_page].
    The query should have a deterministic ORDER BY for stable paging.
    """
    if not isinstance(query, Query):
        raise TypeError("paginate() expects a sqlalchemy.orm.Query; use paginate_select() for Select")

    page = max(1, int(page))
    per_page = min(max(1, int(per_page)), max_per_page)

    # Count over the original query as a subquery so DISTINCT, GROUP BY,
    # and joins are counted correctly. Ordering is dropped for efficiency.
    total = query.order_by(None).count()

    items = query.limit(per_page).offset((page - 1) * per_page).all()
    return items, total


def paginate_select(
    session: Any,
    stmt: Any,
    page: int = 1,
    per_page: int = 20,
    max_per_page: int = 100,
) -> tuple[list[Any], int]:
    """Return (rows, total) for one page of a 2.0-style ``select()`` statement.

    Uses ``session.execute`` and returns row objects (use ``scalars`` semantics
    by selecting a single entity: results are unwrapped when the statement
    selects exactly one column/entity).
    """
    page = max(1, int(page))
    per_page = min(max(1, int(per_page)), max_per_page)

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = session.execute(count_stmt).scalar_one()

    result = session.execute(stmt.limit(per_page).offset((page - 1) * per_page))
    if len(stmt.selected_columns) == 1 or len(stmt.column_descriptions) == 1:
        items = result.scalars().all()
    else:
        items = result.all()
    return items, total
