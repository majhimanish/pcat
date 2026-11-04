"""Tests for security.check_callback_url (loguru and LNbits settings are stubbed)."""
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

settings = types.SimpleNamespace(lnbits_callback_url_rules=[])
stub("loguru", logger=types.SimpleNamespace(debug=lambda msg: None))
stub("lnbits.settings", settings=settings)

from impl import check_callback_url  # noqa: E402


def test_any_http_url_allowed_without_rules():
    settings.lnbits_callback_url_rules = []
    assert check_callback_url("https://shop.example/hook") is None


@pytest.mark.parametrize("url", ["ftp://x.example/", "javascript:alert(1)", "https://user:pw@x.example/",
                                 "https://x.example:99999/", "http:///nohost"])
def test_rejects_bad_schemes_credentials_ports_and_hosts(url):
    settings.lnbits_callback_url_rules = []
    with pytest.raises(ValueError):
        check_callback_url(url)


def test_rules_are_full_matches_on_the_origin():
    settings.lnbits_callback_url_rules = [r"https://([a-z]+\.)?shop\.example", "(invalid"]
    assert check_callback_url("https://api.shop.example/x?y=1") is None
    for url in ("https://shop.example.evil.test/", "http://shop.example/", "https://localhost:8080/"):
        with pytest.raises(ValueError):
            check_callback_url(url)
    settings.lnbits_callback_url_rules = []
