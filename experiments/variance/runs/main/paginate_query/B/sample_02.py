from sqlalchemy import func, select


def paginate(query, page=1, per_page=20):
    """Return (rows, total) for the given 1-based page of a SQLAlchemy query.

    Works with legacy ``Session.query(...)`` Query objects. For 2.0-style
    ``select()`` statements, use ``paginate_select`` with a session.
    """
    page = max(int(page), 1)
    per_page = max(int(per_page), 1)

    # Count over a subquery so joins, group_by, and distinct are handled
    # correctly. Ordering is dropped since it doesn't affect the count.
    total = query.order_by(None).count()

    rows = (
        query.limit(per_page)
        .offset((page - 1) * per_page)
        .all()
    )
    return rows, total


def paginate_select(session, stmt, page=1, per_page=20):
    """Return (rows, total) for the given 1-based page of a 2.0-style select().

    ``rows`` is a list of Row objects (or entities if you call
    ``.scalars()`` yourself; here we use ``session.scalars`` when the
    statement selects a single entity, otherwise ``session.execute``).
    """
    page = max(int(page), 1)
    per_page = max(int(per_page), 1)

    count_stmt = select(func.count()).select_from(
        stmt.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    page_stmt = stmt.limit(per_page).offset((page - 1) * per_page)
    result = session.execute(page_stmt)
    if len(stmt.selected_columns) == 1:
        rows = result.scalars().all()
    else:
        rows = result.all()
    return rows, total
