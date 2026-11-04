"""Tests for security.email_confirm_token (the cache and CTFd are stubbed)."""
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



class Cache(dict):
    def set(self, key, value, timeout=None):
        self[key] = (value, timeout)

    def get(self, key):
        return super().get(key, (None, None))[0]

    def delete(self, key):
        self.pop(key, None)


class UserConfirmTokenInvalidException(Exception):
    pass


CACHE = Cache()
stub("CTFd.cache", cache=CACHE)
stub("CTFd.exceptions.email", UserConfirmTokenInvalidException=UserConfirmTokenInvalidException)
stub("CTFd.utils.encoding", hexencode=lambda b: b.hex())

from impl import generate_email_confirm_token, remove_email_confirm_token, verify_email_confirm_token  # noqa: E402


def test_round_trip_and_single_use():
    token = generate_email_confirm_token("a@example.org")
    assert len(token) == 64 and CACHE[f"confirm_email_{token}"] == ("a@example.org", 1800)
    assert verify_email_confirm_token(token) == "a@example.org"
    remove_email_confirm_token(token)
    with pytest.raises(UserConfirmTokenInvalidException):
        verify_email_confirm_token(token)


def test_tokens_are_random_and_timeout_is_configurable():
    a, b = generate_email_confirm_token("x@y.z", timeout=60), generate_email_confirm_token("x@y.z")
    assert a != b and CACHE[f"confirm_email_{a}"][1] == 60


def test_unknown_token_is_rejected():
    with pytest.raises(UserConfirmTokenInvalidException):
        verify_email_confirm_token("0" * 64)
