from typing import Any, Dict, List, Optional, Union

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session


def paginate(
    query: Union[Query, Any],
    page: int = 1,
    page_size: int = 20,
    session: Optional[Session] = None,
    max_page_size: int = 1000,
) -> Dict[str, Any]:
    """Paginate a SQLAlchemy query.

    Supports legacy ``Query`` objects (session bound to the query) and
    SQLAlchemy 1.4/2.0 ``Select`` statements (requires ``session``).

    Returns a dict with keys: items, total, page, page_size.
    """
    if not isinstance(page, int) or page < 1:
        page = 1
    if not isinstance(page_size, int) or page_size < 1:
        raise ValueError("page_size must be a positive integer")
    page_size = min(page_size, max_page_size)

    offset = (page - 1) * page_size

    if isinstance(query, Query):
        # Count over the query as a subquery so joins, filters,
        # group by and distinct are handled correctly.
        total = query.order_by(None).count()
        items: List[Any] = query.limit(page_size).offset(offset).all()
    else:
        if session is None:
            raise ValueError("session is required when paginating a Select statement")
        count_stmt = select(func.count()).select_from(
            query.order_by(None).subquery()
        )
        total = session.execute(count_stmt).scalar_one()
        result = session.execute(query.limit(page_size).offset(offset))
        # Use scalars() for single-entity selects, rows otherwise.
        if len(query.column_descriptions) == 1:
            items = list(result.scalars().all())
        else:
            items = list(result.all())

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
