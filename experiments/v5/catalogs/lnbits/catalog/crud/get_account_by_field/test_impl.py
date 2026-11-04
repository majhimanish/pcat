"""Tests for crud.get_account_by_field (the LNbits db is stubbed)."""
import asyncio
import sys
import types


def stub(name, **attrs):
    """Register a fake module (and its parents) so impl.py imports without FastAPI or LNbits."""
    parts = name.split(".")
    for i in range(1, len(parts) + 1):
        mod_name = ".".join(parts[:i])
        sys.modules.setdefault(mod_name, types.ModuleType(mod_name))
        if i > 1:
            setattr(sys.modules[".".join(parts[: i - 1])], parts[i - 1], sys.modules[mod_name])
    for key, value in attrs.items():
        setattr(sys.modules[name], key, value)
    return sys.modules[name]


class FakeDb:
    """Records queries; fetchone returns the configured row."""

    def __init__(self, row=None):
        self.row, self.calls = row, []

    async def fetchone(self, sql, params=None, model=None):
        self.calls.append(("fetchone", " ".join(sql.split()), params, model))
        return self.row

    async def execute(self, sql, params=None):
        self.calls.append(("execute", " ".join(sql.split()), params))

DB = FakeDb(row="ACCOUNT")
stub("lnbits.core.db", db=DB)
stub("lnbits.db", Connection=object)
class Account:
    pass


stub("lnbits.core.models", Account=Account)

from impl import get_account_by_username  # noqa: E402


def test_case_insensitive_parameterized_query():
    assert asyncio.run(get_account_by_username("Alice")) == "ACCOUNT"
    kind, sql, params, model = DB.calls[-1]
    assert "LOWER(username) = :username" in sql and params == {"username": "alice", "activated": True}
    assert model is Account


def test_inactive_and_explicit_connection():
    conn = FakeDb(row=None)
    assert asyncio.run(get_account_by_username("bob", active_only=False, conn=conn)) is None
    assert conn.calls[-1][2] == {"username": "bob", "activated": False}


def test_empty_username_short_circuits():
    before = len(DB.calls)
    assert asyncio.run(get_account_by_username("")) is None and len(DB.calls) == before
