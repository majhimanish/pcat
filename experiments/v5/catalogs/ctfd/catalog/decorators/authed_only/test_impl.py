"""Tests for decorators.authed_only (Flask and CTFd are stubbed)."""
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

STATE = {"authed": False}
stub("flask", abort=abort, request=REQUEST, redirect=lambda url: ("redirect", url),
     url_for=lambda endpoint, **kw: f"/{endpoint}?next={kw.get('next')}")
stub("CTFd.utils.user", authed=lambda: STATE["authed"])

from impl import authed_only  # noqa: E402


@authed_only
def page(x):
    return ("page", x)


def test_authenticated_user_passes():
    STATE["authed"] = True
    assert page(1) == ("page", 1) and page.__name__ == "page"


def test_browser_is_redirected_to_login_with_next():
    STATE["authed"] = False
    REQUEST.is_json = False
    assert page(1) == ("redirect", "/auth.login?next=/page?x=1")


@pytest.mark.parametrize("is_json,best", [(True, "text/html"), (False, "text/event-stream")])
def test_api_and_event_stream_requests_get_403(is_json, best):
    STATE["authed"] = False
    REQUEST.is_json, REQUEST.accept_mimetypes.best = is_json, best
    with pytest.raises(Aborted) as exc:
        page(1)
    assert exc.value.code == 403
    REQUEST.is_json, REQUEST.accept_mimetypes.best = False, "text/html"
