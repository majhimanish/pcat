"""Tests for challenges.decay_linear (CTFd models are stubbed)."""
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

SOLVES = {"n": 0}


class Col:
    def __eq__(self, other):
        return True

    __hash__ = object.__hash__


class Query:
    def join(self, *a):
        return self

    def filter(self, *a):
        return self

    def count(self):
        return SOLVES["n"]


Model = types.SimpleNamespace(id=Col(), hidden=Col(), banned=Col())
stub("CTFd.models", Solves=types.SimpleNamespace(query=Query(), account_id=Col(), challenge_id=Col()))
stub("CTFd.utils.modes", get_model=lambda: Model)

from impl import linear  # noqa: E402

CH = types.SimpleNamespace(id=1, initial=500, decay=25, minimum=100)


def test_first_solve_keeps_the_initial_value():
    SOLVES["n"] = 0
    assert linear(CH) == 500
    SOLVES["n"] = 1
    assert linear(CH) == 500


def test_decays_per_solve_and_never_below_minimum():
    SOLVES["n"] = 5
    assert linear(CH) == 400
    SOLVES["n"] = 100
    assert linear(CH) == 100


def test_rounds_up():
    SOLVES["n"] = 2
    assert linear(types.SimpleNamespace(id=1, initial=100, decay=0.5, minimum=0)) == 100
