"""Tests for crud.delete_by_ext_id (the LNbits db is stubbed)."""
import pytest

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

DB = FakeDb()
stub("lnbits.core.db", db=DB)
stub("lnbits.db", Connection=object)

from impl import delete_dbversion  # noqa: E402


def test_deletes_with_a_named_parameter():
    asyncio.run(delete_dbversion(ext_id="lnurlp"))
    assert DB.calls[-1] == ("execute", "DELETE FROM dbversions WHERE db = :ext", {"ext": "lnurlp"})


def test_ext_id_is_keyword_only():
    with pytest.raises(TypeError):
        asyncio.run(delete_dbversion("lnurlp"))
