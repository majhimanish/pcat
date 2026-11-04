"""Tests for api.authorize_read (Django and the app are stubbed)."""
import functools

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



class JsonResponse:
    def __init__(self, data, status=200):
        self.data, self.status = data, status


class Proj:
    api_key_readonly = "r" * 32


KEYS = {"a" * 32: Proj(), "hcr_" + "b" * 28: Proj(), "r" * 32: Proj()}


class Manager:
    def for_api_key(self, key, accept_rw, accept_ro):
        assert accept_rw and accept_ro
        return KEYS.get(key)


class Project:
    objects = Manager()


stub("django.http", HttpRequest=object, HttpResponse=object, JsonResponse=JsonResponse)
stub("hc.accounts.models", Project=Project)
stub("hc.api.decorators", ApiRequest=object)
stub("hc.lib.typealias", ViewFunc=object)

from impl import authorize_read  # noqa: E402


class Request:
    def __init__(self, key=None, path="/api/v3/checks/"):
        self.headers = {"X-Api-Key": key} if key is not None else {}
        self.path_info = path


@authorize_read
def view(request):
    return ("ok", request.project, request.readonly, request.v)


def test_missing_and_malformed_keys_are_401():
    for req in (Request(), Request("short")):
        resp = view(req)
        assert resp.status == 401 and resp.data == {"error": "missing api key"}


def test_wrong_key_is_401():
    resp = view(Request("z" * 32))
    assert resp.status == 401 and resp.data == {"error": "wrong api key"}


def test_read_write_key_and_version():
    assert view(Request("a" * 32)) == ("ok", KEYS["a" * 32], False, 3)
    assert view(Request("a" * 32, "/api/v2/checks/"))[3] == 2
    assert view(Request("a" * 32, "/api/v1/checks/"))[3] == 1


def test_read_only_keys_set_readonly():
    assert view(Request("hcr_" + "b" * 28))[2] is True
    assert view(Request("r" * 32))[2] is True


def test_wraps_keeps_the_view_name():
    assert view.__name__ == "view" and isinstance(view, functools.partial) is False
