from sqlalchemy import func, select
from sqlalchemy.orm import Session


def paginate_query(session: Session, query, page: int = 1, per_page: int = 20):
    """Return (items, total) for the requested page of a SQLAlchemy query.

    `query` may be a legacy `Query` object or a 2.0-style `Select` statement.
    Pages are 1-indexed. The total is the count of all rows the query matches,
    ignoring pagination.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if per_page < 1:
        raise ValueError("per_page must be >= 1")

    offset = (page - 1) * per_page

    if hasattr(query, "statement"):
        # Legacy Query object
        total = query.order_by(None).count()
        items = query.limit(per_page).offset(offset).all()
    else:
        # 2.0-style Select
        count_stmt = select(func.count()).select_from(
            query.order_by(None).subquery()
        )
        total = session.execute(count_stmt).scalar_one()
        items = session.execute(query.limit(per_page).offset(offset)).scalars().all()

    return items, total
