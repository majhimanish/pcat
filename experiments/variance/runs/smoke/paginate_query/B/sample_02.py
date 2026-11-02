from sqlalchemy import func, select
from sqlalchemy.orm import Query


def paginate(query, page=1, per_page=20):
    """Return (rows, total) for the requested 1-based page of `query`.

    Works with a legacy ``Query`` (bound to a session) or a 2.0-style
    ``Select`` paired with a session passed via ``session=``.
    """
    page = max(int(page), 1)
    per_page = max(int(per_page), 1)

    if not isinstance(query, Query):
        raise TypeError("paginate() expects a sqlalchemy.orm.Query bound to a session")

    # Count over a subquery so joins, DISTINCT, and GROUP BY are counted correctly.
    # Ordering is dropped from the count since it is irrelevant and can be costly.
    total = query.order_by(None).with_entities(func.count()).select_from(
        query.order_by(None).subquery()
    ).scalar() or 0

    rows = query.limit(per_page).offset((page - 1) * per_page).all()
    return rows, total


def paginate_select(session, stmt, page=1, per_page=20):
    """Same as ``paginate`` but for a 2.0-style ``select()`` statement."""
    page = max(int(page), 1)
    per_page = max(int(per_page), 1)

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = session.execute(count_stmt).scalar() or 0

    rows = session.execute(
        stmt.limit(per_page).offset((page - 1) * per_page)
    ).scalars().all()
    return rows, total
