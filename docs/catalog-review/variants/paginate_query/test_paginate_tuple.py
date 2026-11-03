import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import String, create_engine, select  # noqa: E402
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column  # noqa: E402

from paginate_tuple import paginate  # noqa: E402


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20))
    team: Mapped[str] = mapped_column(String(5))


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all(User(id=i, name=f"user{i:02d}", team="a" if i % 2 else "b") for i in range(1, 26))
        s.commit()
        yield s


def page(session, stmt, **kw):
    items, total = paginate(session, stmt, **kw)
    return items, total


def test_pages_cover_all_rows_once(session):
    stmt = select(User).order_by(User.id)
    seen = []
    for n in (1, 2, 3):
        items, total = page(session, stmt, page=n, page_size=10)
        assert total == 25 and all(isinstance(u, User) for u in items)
        seen += [u.id for u in items]
    assert seen == list(range(1, 26))


def test_last_partial_and_past_end_pages(session):
    stmt = select(User).order_by(User.id)
    assert [u.id for u in page(session, stmt, page=3, page_size=10)[0]] == [21, 22, 23, 24, 25]
    assert page(session, stmt, page=9, page_size=10) == ([], 25)


def test_filtered_count_and_column_select(session):
    stmt = select(User.id, User.name).where(User.team == "a").order_by(User.id.desc())
    items, total = page(session, stmt, page=1, page_size=3)
    assert total == 13 and [tuple(r) for r in items] == [(25, "user25"), (23, "user23"), (21, "user21")]


def test_grouped_query_counts_groups(session):
    stmt = select(User.team, sqlalchemy.func.count()).group_by(User.team).order_by(User.team)
    items, total = page(session, stmt)
    assert total == 2 and [tuple(r) for r in items] == [("a", 13), ("b", 12)]


def test_empty_result(session):
    assert page(session, select(User).where(User.id > 100).order_by(User.id)) == ([], 0)


@pytest.mark.parametrize("kw,msg", [({"page": 0}, "page must"), ({"page_size": 0}, "between"),
                                     ({"page_size": 101}, "between")])
def test_rejects_bad_paging(session, kw, msg):
    with pytest.raises(ValueError, match=msg):
        paginate(session, select(User).order_by(User.id), **kw)
