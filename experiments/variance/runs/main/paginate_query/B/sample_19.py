from typing import Any, Dict

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def get_page(
    session: Session,
    query: Any,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """
    Return page `page` (1-based) of `query` along with the total row count.

    `query` is a SQLAlchemy 2.0 Select statement (e.g. select(User).order_by(User.id)).
    Provide a deterministic ORDER BY so pages are stable.

    Returns:
        {
            "items": list of rows/entities for the requested page,
            "total": total number of rows matching the query (ignoring pagination),
            "page": the page number,
            "page_size": the page size,
            "pages": total number of pages,
        }
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    # Count over the query as a subquery (works with joins, distinct, group by).
    # Strip ordering for efficiency.
    count_stmt = select(func.count()).select_from(
        query.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    page_stmt = query.limit(page_size).offset((page - 1) * page_size)
    result = session.execute(page_stmt)

    # scalars() for single-entity selects; fall back to rows for multi-column selects.
    if len(query.selected_columns) == 1 and len(query.column_descriptions) == 1:
        items = result.scalars().all()
    else:
        items = result.all()

    pages = (total + page_size - 1) // page_size

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }
