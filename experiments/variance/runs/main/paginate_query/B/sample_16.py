from sqlalchemy import func, select
from sqlalchemy.orm import Query


def paginate(query, page=1, page_size=20):
    """Return (items, total) for the given 1-based page of a SQLAlchemy query.

    Works with legacy ``Query`` objects (Session.query(...)) and with
    2.0-style ``Select`` statements (in which case a ``session`` must be
    supplied via ``paginate_select``).
    """
    if not isinstance(query, Query):
        raise TypeError(
            "paginate() expects a sqlalchemy.orm.Query; "
            "use paginate_select() for Select statements"
        )
    page = max(1, int(page))
    page_size = max(1, int(page_size))

    total = query.order_by(None).count()
    items = query.limit(page_size).offset((page - 1) * page_size).all()
    return items, total


def paginate_select(session, stmt, page=1, page_size=20):
    """Return (items, total) for the given 1-based page of a 2.0-style Select."""
    page = max(1, int(page))
    page_size = max(1, int(page_size))

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = session.execute(count_stmt).scalar_one()

    page_stmt = stmt.limit(page_size).offset((page - 1) * page_size)
    items = session.execute(page_stmt).scalars().all()
    return items, total
