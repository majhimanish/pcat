"""Tests for auth.lnbits_access_token (LNbits settings are stubbed; needs pyjwt)."""
import datetime as dt

import pytest

jwt = pytest.importorskip("jwt")
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

settings = types.SimpleNamespace(auth_token_expire_minutes=60, auth_secret_key="k" * 32)
stub("lnbits.settings", settings=settings)

from impl import create_access_token  # noqa: E402


def test_signed_hs256_with_expiry_and_no_none_claims():
    token = create_access_token({"sub": "alice", "usr": "u1", "extra": None})
    claims = jwt.decode(token, "k" * 32, algorithms=["HS256"])
    assert claims["sub"] == "alice" and claims["usr"] == "u1" and "extra" not in claims
    exp = dt.datetime.fromtimestamp(claims["exp"], dt.timezone.utc)
    assert dt.timedelta(minutes=59) < exp - dt.datetime.now(dt.timezone.utc) <= dt.timedelta(minutes=60)


def test_custom_expiry_and_wrong_key_rejected():
    token = create_access_token({"sub": "a"}, token_expire_minutes=5)
    claims = jwt.decode(token, "k" * 32, algorithms=["HS256"])
    assert claims["exp"] - dt.datetime.now(dt.timezone.utc).timestamp() <= 5 * 60
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "other" * 8, algorithms=["HS256"])
