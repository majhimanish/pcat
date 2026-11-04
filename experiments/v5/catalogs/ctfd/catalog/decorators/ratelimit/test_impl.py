"""Tests for decorators.ratelimit (Flask, the cache and CTFd are stubbed)."""
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



class Cache(dict):
    def get(self, key):
        return super().get(key)

    def set(self, key, value, timeout=None):
        self[key] = value
        self.timeouts = getattr(self, "timeouts", {})
        self.timeouts[key] = timeout


class Resp(dict):
    status_code = 200


CACHE = Cache()
IP = {"ip": "1.2.3.4"}
stub("flask", request=REQUEST, jsonify=lambda data: Resp(data))
stub("CTFd.cache", cache=CACHE)
stub("CTFd.utils.user", get_ip=lambda: IP["ip"])

from impl import ratelimit  # noqa: E402


@ratelimit(method="POST", limit=3, interval=60)
def login():
    return "ok"


def test_counts_per_ip_and_endpoint_and_returns_429():
    CACHE.clear()
    REQUEST.method, REQUEST.endpoint = "POST", "auth.login"
    assert [login() for _ in range(3)] == ["ok", "ok", "ok"]
    blocked = login()
    assert blocked.status_code == 429 and blocked["code"] == 429 and "3 requests in 60 seconds" in blocked["message"]
    assert CACHE["rl:1.2.3.4:auth.login"] == 3 and CACHE.timeouts["rl:1.2.3.4:auth.login"] == 60
    IP["ip"] = "5.6.7.8"
    assert login() == "ok"  # another client is not affected
    IP["ip"] = "1.2.3.4"


def test_other_methods_are_not_counted():
    CACHE.clear()
    REQUEST.method = "GET"
    assert [login() for _ in range(10)] == ["ok"] * 10 and not CACHE
    REQUEST.method = "POST"
