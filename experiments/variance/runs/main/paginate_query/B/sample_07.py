from sqlalchemy import func, select
from sqlalchemy.orm import Session


def paginate(query, page, per_page, session=None):
    """Return (rows, total) for the requested 1-indexed page of `query`.

    `query` may be a legacy `Query` object (bound to a session) or a 2.0-style
    `Select` statement (in which case `session` must be provided).
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if per_page < 1:
        raise ValueError("per_page must be >= 1")

    offset = (page - 1) * per_page

    # Legacy Query object
    if hasattr(query, "session") and hasattr(query, "limit") and not hasattr(query, "subquery") is False:
        pass

    if hasattr(query, "with_entities") and hasattr(query, "offset"):
        # Count over a subquery so GROUP BY / DISTINCT / joins are counted correctly
        total = query.order_by(None).count()
        rows = query.limit(per_page).offset(offset).all()
        return rows, total

    # 2.0-style Select
    if session is None:
        raise ValueError("session is required when query is a Select statement")

    count_stmt = select(func.count()).select_from(query.order_by(None).subquery())
    total = session.execute(count_stmt).scalar_one()
    rows = session.execute(query.limit(per_page).offset(offset)).scalars().all()
    return rows, total
