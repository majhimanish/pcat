"""Tests for user.cached_lookup (the cache and CTFd models are stubbed)."""
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



class Cache:
    def __init__(self):
        self.timeouts = []

    def memoize(self, timeout=None):
        self.timeouts.append(timeout)
        return lambda f: f


class Query:
    def __init__(self, rows):
        self.rows, self.kw = rows, None

    def filter_by(self, **kw):
        self.kw = kw
        return self

    def first(self):
        return self.rows.get(self.kw["id"])


CACHE = Cache()
TEAMS = {1: types.SimpleNamespace(place="1st")}
stub("CTFd.cache", cache=CACHE)
stub("CTFd.models", Teams=types.SimpleNamespace(query=Query(TEAMS)))

from impl import get_team_place  # noqa: E402


def test_returns_attribute_or_none_and_is_memoized():
    assert get_team_place(1) == "1st" and get_team_place(2) is None
    assert CACHE.timeouts == [300]
