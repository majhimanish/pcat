from sqlalchemy import func, select
from sqlalchemy.orm import Query


def paginate(query, page=1, page_size=20):
    """Return (items, total) for the given 1-based page of a query.

    Works with legacy ORM `Query` objects as well as 2.0-style `Select`
    statements (for the latter, pass a Session as `session` via
    `paginate_select`).
    """
    if not isinstance(query, Query):
        raise TypeError("paginate expects a sqlalchemy.orm.Query; use paginate_select for Select statements")

    page = max(int(page), 1)
    page_size = max(int(page_size), 1)

    total = query.order_by(None).count()
    items = query.limit(page_size).offset((page - 1) * page_size).all()
    return items, total


def paginate_select(session, stmt, page=1, page_size=20, scalars=True):
    """Return (items, total) for the given 1-based page of a 2.0-style Select.

    If `scalars` is True, items are ORM entities / first-column scalars;
    otherwise they are Row objects.
    """
    page = max(int(page), 1)
    page_size = max(int(page_size), 1)

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = session.execute(count_stmt).scalar_one()

    paged = stmt.limit(page_size).offset((page - 1) * page_size)
    result = session.execute(paged)
    items = result.scalars().all() if scalars else result.all()
    return items, total
