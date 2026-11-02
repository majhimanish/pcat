from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session
from sqlalchemy.sql import Select


def paginate(
    query: Any,
    page: int = 1,
    page_size: int = 20,
    session: Optional[Session] = None,
    max_page_size: int = 1000,
) -> Dict[str, Any]:
    """Paginate a SQLAlchemy query.

    Works with legacy ``Query`` objects (bound to a session) and with
    2.0-style ``Select`` statements (a ``session`` must then be provided).

    Returns a dict with keys: ``items``, ``total``, ``page`` and ``page_size``.
    """
    page = max(1, int(page))
    page_size = min(max(1, int(page_size)), max_page_size)
    offset = (page - 1) * page_size

    items: List[Any]
    if isinstance(query, Query):
        # Count over a subquery so GROUP BY / DISTINCT / joins are handled correctly.
        total = query.order_by(None).count()
        items = query.limit(page_size).offset(offset).all()
    elif isinstance(query, Select):
        if session is None:
            raise ValueError("A session is required when paginating a Select statement.")
        count_stmt = select(func.count()).select_from(
            query.order_by(None).subquery()
        )
        total = session.execute(count_stmt).scalar_one()
        result = session.execute(query.limit(page_size).offset(offset))
        # Return ORM entities for single-entity selects, rows otherwise.
        if len(query.column_descriptions) == 1:
            items = list(result.scalars().all())
        else:
            items = list(result.all())
    else:
        raise TypeError("query must be a sqlalchemy.orm.Query or sqlalchemy.sql.Select")

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
