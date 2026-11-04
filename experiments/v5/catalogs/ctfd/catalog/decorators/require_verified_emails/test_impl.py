"""Tests for decorators.require_verified_emails (Flask and CTFd are stubbed)."""
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

CFG, USER = {"verify_emails": True}, {"authed": True, "admin": False, "verified": False}
stub("flask", abort=abort, request=REQUEST, redirect=lambda url: ("redirect", url), url_for=lambda e, **k: f"/{e}")
stub("CTFd.utils", get_config=lambda key: CFG.get(key))
stub("CTFd.utils.user", authed=lambda: USER["authed"], is_admin=lambda: USER["admin"],
     is_verified=lambda: USER["verified"])

from impl import require_verified_emails  # noqa: E402


@require_verified_emails
def view():
    return "view"


def test_unverified_user_redirected_or_403():
    USER.update(authed=True, admin=False, verified=False)
    assert view() == ("redirect", "/auth.confirm")
    REQUEST.is_json = True
    with pytest.raises(Aborted):
        view()
    REQUEST.is_json = False


def test_verified_admins_anonymous_or_disabled_pass():
    for update in ({"verified": True}, {"admin": True}, {"authed": False}):
        USER.update(authed=True, admin=False, verified=False)
        USER.update(update)
        assert view() == "view"
    USER.update(authed=True, admin=False, verified=False)
    CFG["verify_emails"] = False
    assert view() == "view"
    CFG["verify_emails"] = True
