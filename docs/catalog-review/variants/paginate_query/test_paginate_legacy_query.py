import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import String, create_engine, func  # noqa: E402
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column  # noqa: E402

from paginate_legacy_query import paginate  # noqa: E402


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(5))


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all(Item(id=i, kind="x" if i % 3 else "y") for i in range(1, 26))
        s.commit()
        yield s


def test_pages_cover_all_rows_once(session):
    query = session.query(Item).order_by(Item.id)
    seen = []
    for n in (1, 2, 3):
        items, total = paginate(query, page=n, page_size=10)
        assert total == 25
        seen += [i.id for i in items]
    assert seen == list(range(1, 26))
    assert paginate(query, page=4, page_size=10) == ([], 25)


def test_filtered_and_grouped_counts(session):
    filtered = session.query(Item).filter(Item.kind == "y").order_by(Item.id.desc())
    items, total = paginate(filtered, page=1, page_size=2)
    assert total == 8 and [i.id for i in items] == [24, 21]
    grouped = session.query(Item.kind, func.count()).group_by(Item.kind).order_by(Item.kind)
    assert paginate(grouped) == ([("x", 17), ("y", 8)], 2)


@pytest.mark.parametrize("kw", [{"page": 0}, {"page_size": 0}, {"page_size": 101}])
def test_rejects_bad_paging(session, kw):
    with pytest.raises(ValueError):
        paginate(session.query(Item), **kw)
