from sqlalchemy import func, select
from sqlalchemy.orm import Query


def paginate(query, page=1, per_page=20, max_per_page=100):
    """Return (items, total) for the requested page of a SQLAlchemy query.

    Supports legacy ``Query`` objects as well as 2.0-style ``Select``
    statements (the latter requires a ``Session`` to be passed via
    ``paginate_select``).

    ``page`` is 1-based. Invalid or out-of-range values are clamped.
    The query should have a deterministic ORDER BY for stable paging.
    """
    if not isinstance(query, Query):
        raise TypeError("paginate expects a sqlalchemy.orm.Query; use paginate_select for Select statements")

    page = max(int(page), 1)
    per_page = min(max(int(per_page), 1), max_per_page)

    total = query.order_by(None).count()
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    return items, total


def paginate_select(session, stmt, page=1, per_page=20, max_per_page=100):
    """Return (items, total) for the requested page of a 2.0-style Select."""
    page = max(int(page), 1)
    per_page = min(max(int(per_page), 1), max_per_page)

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = session.execute(count_stmt).scalar_one()

    rows = session.execute(stmt.limit(per_page).offset((page - 1) * per_page))
    items = rows.scalars().all()
    return items, total
