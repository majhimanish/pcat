from typing import Any, Dict, List, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Query
from sqlalchemy.sql import Select

T = TypeVar("T")


def _normalize_pagination(page: int, page_size: int, max_page_size: int) -> tuple[int, int]:
    """Clamp page and page_size to valid values."""
    page = max(1, int(page))
    page_size = min(max(1, int(page_size)), max_page_size)
    return page, page_size


def paginate(
    query: Query,
    page: int = 1,
    page_size: int = 20,
    max_page_size: int = 100,
) -> Dict[str, Any]:
    """
    Paginate a legacy SQLAlchemy ORM Query.

    Returns a dict with keys: items, total, page, page_size.
    The query should already include any filters and ordering.
    """
    page, page_size = _normalize_pagination(page, page_size, max_page_size)

    # Count on a subquery with ordering removed so it works with
    # joins, group_by, and distinct without double counting.
    total = query.order_by(None).count()

    items: List[Any] = (
        query.limit(page_size).offset((page - 1) * page_size).all()
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def paginate_select(
    session,
    stmt: Select,
    page: int = 1,
    page_size: int = 20,
    max_page_size: int = 100,
    scalars: bool = True,
) -> Dict[str, Any]:
    """
    Paginate a SQLAlchemy 2.0 style select() statement.

    Returns a dict with keys: items, total, page, page_size.
    Set scalars=False to get Row objects instead of scalar entities
    (useful when selecting multiple columns or entities).
    """
    page, page_size = _normalize_pagination(page, page_size, max_page_size)

    count_stmt = select(func.count()).select_from(
        stmt.order_by(None).subquery()
    )
    total = session.execute(count_stmt).scalar_one()

    paged_stmt = stmt.limit(page_size).offset((page - 1) * page_size)
    result = session.execute(paged_stmt)
    items: List[Any] = result.scalars().all() if scalars else result.all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
