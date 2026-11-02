from sqlalchemy import func, select


def paginate(query, page, per_page):
    """Return (rows, total) for the given 1-based page of a SQLAlchemy query.

    `query` may be a legacy `Query` object (with a `.session`) or a 2.0-style
    `Select` statement (in which case `session` must be supplied via
    `paginate_select`).
    """
    page = max(int(page), 1)
    per_page = max(int(per_page), 1)

    total = query.order_by(None).count()
    rows = (
        query.limit(per_page)
        .offset((page - 1) * per_page)
        .all()
    )
    return rows, total


def paginate_select(session, stmt, page, per_page):
    """Return (rows, total) for the given 1-based page of a 2.0-style Select."""
    page = max(int(page), 1)
    per_page = max(int(per_page), 1)

    count_stmt = select(func.count()).select_from(
        stmt.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    page_stmt = stmt.limit(per_page).offset((page - 1) * per_page)
    rows = session.execute(page_stmt).scalars().all()
    return rows, total
