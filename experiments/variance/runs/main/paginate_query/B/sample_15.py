from math import ceil
from typing import Any, Dict, List, Optional, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Query


def paginate(
    query: Query,
    page: int = 1,
    page_size: int = 20,
    max_page_size: Optional[int] = 100,
    transform: Optional[Callable[[Any], Any]] = None,
) -> Dict[str, Any]:
    """
    Paginate a SQLAlchemy ORM Query.

    Args:
        query: A SQLAlchemy ORM Query (ordering should be applied by the caller
            for deterministic results).
        page: 1-based page number. Values < 1 are coerced to 1.
        page_size: Number of items per page. Values < 1 are coerced to 1 and
            capped at max_page_size if provided.
        max_page_size: Upper bound on page_size (None disables the cap).
        transform: Optional function applied to each item before returning.

    Returns:
        A dict with keys: items, total, page, page_size, pages.
    """
    try:
        page = int(page)
        page_size = int(page_size)
    except (TypeError, ValueError):
        raise ValueError("page and page_size must be integers")

    page = max(page, 1)
    page_size = max(page_size, 1)
    if max_page_size is not None:
        page_size = min(page_size, max_page_size)

    # Count over a subquery so DISTINCT / GROUP BY / joins are counted correctly;
    # drop ordering since it is irrelevant for counting.
    total = (
        query.order_by(None)
        .with_entities(func.count())
        .select_from(query.order_by(None).subquery())
        .scalar()
    ) or 0

    items: List[Any] = (
        query.limit(page_size).offset((page - 1) * page_size).all()
        if total
        else []
    )

    if transform is not None:
        items = [transform(item) for item in items]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": ceil(total / page_size) if total else 0,
    }


def paginate_select(
    session: Any,
    stmt: Any,
    page: int = 1,
    page_size: int = 20,
    max_page_size: Optional[int] = 100,
    scalars: bool = True,
) -> Dict[str, Any]:
    """
    Paginate a SQLAlchemy 2.0-style select() statement using a Session.

    Args:
        session: A SQLAlchemy Session.
        stmt: A select() statement.
        page: 1-based page number.
        page_size: Items per page (capped by max_page_size).
        max_page_size: Upper bound for page_size (None disables the cap).
        scalars: If True, return scalar results (e.g. ORM entities);
            otherwise return Row objects.

    Returns:
        A dict with keys: items, total, page, page_size, pages.
    """
    page = max(int(page), 1)
    page_size = max(int(page_size), 1)
    if max_page_size is not None:
        page_size = min(page_size, max_page_size)

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = session.execute(count_stmt).scalar() or 0

    items: List[Any] = []
    if total:
        page_stmt = stmt.limit(page_size).offset((page - 1) * page_size)
        result = session.execute(page_stmt)
        items = list(result.scalars().all() if scalars else result.all())

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": ceil(total / page_size) if total else 0,
    }
