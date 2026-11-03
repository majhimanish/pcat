from sqlalchemy import func, select
from sqlalchemy.orm import Query


def paginate(query, page=1, per_page=20):
    """Return (items, total) for the given 1-based page of a query.

    Works with legacy ``Query`` objects (Session.query(...)). For 2.0-style
    ``Select`` statements, use ``paginate_select`` instead.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if per_page < 1:
        raise ValueError("per_page must be >= 1")
    if not isinstance(query, Query):
        raise TypeError("query must be a sqlalchemy.orm.Query; use paginate_select for Select")

    total = query.order_by(None).count()
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    return items, total


def paginate_select(session, stmt, page=1, per_page=20, scalars=True):
    """Return (items, total) for the given 1-based page of a 2.0-style Select.

    If ``scalars`` is True, items are the first column/entity of each row
    (typical for ORM entities); otherwise full Row objects are returned.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if per_page < 1:
        raise ValueError("per_page must be >= 1")

    count_stmt = select(func.count()).select_from(
        stmt.order_by(None).limit(None).offset(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    page_stmt = stmt.limit(per_page).offset((page - 1) * per_page)
    result = session.execute(page_stmt)
    items = result.scalars().all() if scalars else result.all()
    return items, total
