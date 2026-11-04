"""Tests for decorators.admins_only (Flask and CTFd are stubbed)."""
import pytest

import sys
import types


def stub(name, **attrs):
    """Register a fake module (and its parents) so impl.py imports without Flask or CTFd."""
    parts = name.split(".")
    for i in range(1, len(parts) + 1):
        mod_name = ".".join(parts[:i])
        sys.modules.setdefault(mod_name, types.ModuleType(mod_name))
        if i > 1:
            setattr(sys.modules[".".join(parts[: i - 1])], parts[i - 1], sys.modules[mod_name])
    for key, value in attrs.items():
        setattr(sys.modules[name], key, value)
    return sys.modules[name]


class Aborted(Exception):
    def __init__(self, code):
        self.code = code


def abort(code, description=None):
    raise Aborted(code)


REQUEST = types.SimpleNamespace(is_json=False, full_path="/page?x=1", method="GET", endpoint="views.page",
                                accept_mimetypes=types.SimpleNamespace(best="text/html"))

STATE = {"admin": False}
stub("flask", abort=abort, request=REQUEST, redirect=lambda url: ("redirect", url),
     url_for=lambda endpoint, **kw: f"/{endpoint}?next={kw.get('next')}")
stub("CTFd.utils.user", is_admin=lambda: STATE["admin"])

from impl import admins_only  # noqa: E402


@admins_only
def admin_page():
    return "admin"


def test_admin_passes():
    STATE["admin"] = True
    assert admin_page() == "admin"


def test_non_admin_browser_redirected_and_api_403():
    STATE["admin"] = False
    assert admin_page() == ("redirect", "/auth.login?next=/page?x=1")
    REQUEST.is_json = True
    with pytest.raises(Aborted):
        admin_page()
    REQUEST.is_json = False
