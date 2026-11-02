from sqlalchemy import func, select
from sqlalchemy.orm import Query


def paginate(query, page=1, per_page=20):
    """Return (rows, total) for the requested page of `query`.

    Works with both legacy ``Query`` objects (needs ``.session``) and
    2.0-style ``Select`` statements (requires a Session passed via
    ``paginate_select`` below).

    - ``page`` is 1-indexed; values < 1 are clamped to 1.
    - ``per_page`` values < 1 are clamped to 1.
    - ``total`` is the count of all rows matching the query, ignoring
      limit/offset/order_by.
    """
    page = max(int(page), 1)
    per_page = max(int(per_page), 1)

    if not isinstance(query, Query):
        raise TypeError(
            "paginate() expects a sqlalchemy.orm.Query; "
            "use paginate_select() for 2.0-style select() statements."
        )

    # Count over a subquery so GROUP BY, DISTINCT and joins are counted correctly.
    total = query.order_by(None).count()

    rows = (
        query.limit(per_page)
        .offset((page - 1) * per_page)
        .all()
    )
    return rows, total


def paginate_select(session, stmt, page=1, per_page=20):
    """Return (rows, total) for a 2.0-style ``select()`` statement.

    ``rows`` are ORM entities when the statement selects a single entity
    (via ``scalars()``), otherwise ``Row`` tuples.
    """
    page = max(int(page), 1)
    per_page = max(int(per_page), 1)

    count_stmt = select(func.count()).select_from(
        stmt.order_by(None).limit(None).offset(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    result = session.execute(
        stmt.limit(per_page).offset((page - 1) * per_page)
    )
    if len(stmt.selected_columns) == 1:
        rows = result.scalars().all()
    else:
        rows = result.all()
    return rows, total
