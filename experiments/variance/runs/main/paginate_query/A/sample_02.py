from sqlalchemy import func, select
from sqlalchemy.orm import Session


def paginate_query(session: Session, query, page: int = 1, page_size: int = 20):
    """Return (items, total_count) for the requested page of a SQLAlchemy query.

    `query` may be a legacy Query object or a 2.0-style Select statement.
    `page` is 1-based.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    offset = (page - 1) * page_size

    # Legacy Query object
    if hasattr(query, "count") and hasattr(query, "limit"):
        total = query.order_by(None).count()
        items = query.limit(page_size).offset(offset).all()
        return items, total

    # 2.0-style Select statement
    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()
    items = session.execute(query.limit(page_size).offset(offset)).scalars().all()
    return items, total
