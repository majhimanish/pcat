"""Tests for crud.count_rows (the LNbits db is stubbed)."""
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

DB = FakeDb(row={"count": "7"})
stub("lnbits.core.db", db=DB)
stub("lnbits.db", Connection=object)

from impl import get_accounts_count  # noqa: E402


def test_counts_and_defaults_to_zero():
    assert asyncio.run(get_accounts_count()) == 7
    assert DB.calls[-1][1] == "SELECT COUNT(*) as count FROM accounts"
    assert asyncio.run(get_accounts_count(conn=FakeDb(row=None))) == 0
