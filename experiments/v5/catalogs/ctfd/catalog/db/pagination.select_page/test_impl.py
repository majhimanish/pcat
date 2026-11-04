import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import ForeignKey, String, create_engine, event, func, select  # noqa: E402
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column  # noqa: E402

from impl import paginate  # noqa: E402


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all([Team(id=1), Team(id=2)])
        s.add_all(User(id=i, name=f"user{i:02d}", team_id=1 if i % 2 else 2) for i in range(1, 26))
        s.commit()
        yield s


ORDERED = select(User).order_by(User.id)


# Normal cases ---------------------------------------------------------------
def test_first_page_and_metadata(session):
    page = paginate(session, ORDERED, page=1, page_size=10)
    assert [u.id for u in page["items"]] == list(range(1, 11))
    assert all(isinstance(u, User) for u in page["items"])
    assert {k: v for k, v in page.items() if k != "items"} == {
        "total": 25, "page": 1, "page_size": 10, "pages": 3}


def test_pages_cover_every_row_exactly_once(session):
    seen = [u.id for n in (1, 2, 3) for u in paginate(session, ORDERED, page=n, page_size=10)["items"]]
    assert seen == list(range(1, 26))


def test_defaults_page_1_size_20(session):
    page = paginate(session, ORDERED)
    assert (page["page"], page["page_size"], len(page["items"]), page["pages"]) == (1, 20, 20, 2)


# Edge cases -----------------------------------------------------------------------
def test_last_partial_page_and_past_the_end(session):
    assert [u.id for u in paginate(session, ORDERED, page=3, page_size=10)["items"]] == [21, 22, 23, 24, 25]
    beyond = paginate(session, ORDERED, page=50, page_size=10)
    assert beyond["items"] == [] and beyond["total"] == 25 and beyond["pages"] == 3


def test_exact_multiple_and_single_page(session):
    assert paginate(session, ORDERED, page=1, page_size=25)["pages"] == 1
    assert paginate(session, ORDERED, page=5, page_size=5)["pages"] == 5


def test_empty_result(session):
    page = paginate(session, select(User).where(User.id < 0).order_by(User.id))
    assert (page["items"], page["total"], page["pages"]) == ([], 0, 0)


def test_filtered_join_and_column_selects(session):
    stmt = (select(User.id, User.name).join(Team).where(Team.id == 1).order_by(User.id.desc()))
    page = paginate(session, stmt, page=2, page_size=3)
    assert page["total"] == 13 and [tuple(r) for r in page["items"]] == [
        (19, "user19"), (17, "user17"), (15, "user15")]


def test_grouped_select_counts_groups(session):
    stmt = select(User.team_id, func.count()).group_by(User.team_id).order_by(User.team_id)
    page = paginate(session, stmt)
    assert page["total"] == 2 and [tuple(r) for r in page["items"]] == [(1, 13), (2, 12)]


def test_count_query_ignores_order_by(session):
    statements = []
    event.listen(session.get_bind(), "before_cursor_execute",
                 lambda conn, cur, sql, params, ctx, many: statements.append(sql))
    paginate(session, ORDERED, page=1, page_size=5)
    count_sql = next(s for s in statements if "count(" in s.lower())
    assert "order by" not in count_sql.lower()


# Failure cases / limits ---------------------------------------------------------
@pytest.mark.parametrize("kw,message", [
    ({"page": 0}, "page must be >= 1"), ({"page": -3}, "page must be >= 1"),
    ({"page_size": 0}, "between 1 and 100"), ({"page_size": 101}, "between 1 and 100")])
def test_rejects_bad_paging(session, kw, message):
    with pytest.raises(ValueError, match=message):
        paginate(session, ORDERED, **kw)


def test_page_size_cap_prevents_dumping_the_table(session):
    assert len(paginate(session, ORDERED, page=1, page_size=100)["items"]) == 25
    with pytest.raises(ValueError):
        paginate(session, ORDERED, page_size=10_000)
