"""Tests for auth.check_admin (FastAPI and LNbits are stubbed)."""
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



class HTTPException(Exception):
    def __init__(self, status, detail):
        self.status, self.detail = status, detail


settings = types.SimpleNamespace(super_user="su", lnbits_admin_users=["ad"])
stub("fastapi", Depends=lambda f: None)
stub("fastapi.exceptions", HTTPException=HTTPException)
stub("lnbits.core.models", Account=object)
stub("lnbits.decorators", check_account_exists=lambda: None)
stub("lnbits.settings", settings=settings)

from impl import check_admin  # noqa: E402


def acct(uid, has_password=True):
    return types.SimpleNamespace(id=uid, has_password=has_password)


def test_super_user_and_admins_pass():
    for uid in ("su", "ad"):
        a = acct(uid)
        assert asyncio.run(check_admin(a)) is a


def test_others_and_admins_without_password_get_403():
    for account, words in ((acct("x"), "No admin privileges"), (acct("ad", has_password=False), "credentials")):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(check_admin(account))
        assert exc.value.status == 403 and words in exc.value.detail
