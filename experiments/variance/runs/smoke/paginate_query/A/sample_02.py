from sqlalchemy import func, select
from sqlalchemy.orm import Query


def paginate_query(query, page=1, per_page=20, session=None):
    """Return (items, total) for one page of a SQLAlchemy query.

    Works with legacy `Query` objects and 2.0-style `Select` statements.
    For `Select` statements, a `session` is required.

    - page is 1-indexed; values < 1 are treated as 1.
    - per_page values < 1 raise ValueError.
    - total is the count of all rows matching the query, ignoring pagination.
    """
    if per_page < 1:
        raise ValueError("per_page must be >= 1")
    page = max(1, int(page))
    offset = (page - 1) * per_page

    if isinstance(query, Query):
        total = query.order_by(None).count()
        items = query.limit(per_page).offset(offset).all()
        return items, total

    if session is None:
        raise ValueError("session is required when paginating a Select statement")

    count_stmt = select(func.count()).select_from(query.order_by(None).subquery())
    total = session.execute(count_stmt).scalar_one()
    items = session.execute(query.limit(per_page).offset(offset)).scalars().all()
    return items, total
