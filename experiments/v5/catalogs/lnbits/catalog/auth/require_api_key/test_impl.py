"""Tests for auth.require_api_key (FastAPI and LNbits are stubbed)."""
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

SEEN = []


class KeyChecker:
    def __init__(self, api_key, expected_key_type):
        self.api_key, self.expected = api_key, expected_key_type

    async def __call__(self, request):
        SEEN.append((self.api_key, self.expected, request))
        return "WALLET"


stub("fastapi", Request=object, Security=lambda scheme: None)
stub("lnbits.core.models", KeyType=types.SimpleNamespace(admin="admin", invoice="invoice"), WalletTypeInfo=object)
stub("lnbits.decorators", KeyChecker=KeyChecker, api_key_header="HEADER", api_key_query="QUERY")

from impl import require_admin_key  # noqa: E402


def test_header_key_preferred_and_checked_as_admin():
    assert asyncio.run(require_admin_key("req", api_key_header="h", api_key_query="q")) == "WALLET"
    assert SEEN[-1] == ("h", "admin", "req")


def test_falls_back_to_query_key():
    asyncio.run(require_admin_key("req", api_key_header=None, api_key_query="q"))
    assert SEEN[-1][0] == "q"
