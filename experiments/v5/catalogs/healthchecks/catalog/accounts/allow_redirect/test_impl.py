"""Tests for accounts.allow_redirect (django.urls is stubbed)."""
import sys
import types


def stub(name, **attrs):
    """Register a fake module (and its parents) so impl.py imports without Django or the app."""
    parts = name.split(".")
    for i in range(1, len(parts) + 1):
        mod_name = ".".join(parts[:i])
        sys.modules.setdefault(mod_name, types.ModuleType(mod_name))
        if i > 1:
            setattr(sys.modules[".".join(parts[: i - 1])], parts[i - 1], sys.modules[mod_name])
    for key, value in attrs.items():
        setattr(sys.modules[name], key, value)
    return sys.modules[name]



class Resolver404(Exception):
    pass


ROUTES = {"/checks/": "hc-checks", "/accounts/profile/": "hc-profile"}


def resolve(path):
    if path not in ROUTES:
        raise Resolver404
    return types.SimpleNamespace(url_name=ROUTES[path])


stub("django.urls", Resolver404=Resolver404, resolve=resolve)

from impl import _allow_redirect  # noqa: E402


def test_allowed_relative_route():
    assert _allow_redirect("/checks/") is True
    assert _allow_redirect("/checks/?sort=name") is True


def test_rejects_empty_absolute_and_scheme_relative_urls():
    for url in (None, "", "https://evil.example/checks/", "//evil.example/checks/"):
        assert _allow_redirect(url) is False


def test_rejects_unknown_and_not_allowlisted_routes():
    assert _allow_redirect("/nope/") is False
    assert _allow_redirect("/accounts/profile/") is False
