"""Tests for badges.check_signature (Django is stubbed with an HMAC equivalent)."""
import base64
import hashlib
import hmac

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



def base64_hmac(salt, value, key, algorithm="sha1"):
    digest = hmac.new((salt + key).encode(), value.encode(), getattr(hashlib, algorithm)).digest()
    return base64.urlsafe_b64encode(digest).decode()


stub("django.conf", settings=types.SimpleNamespace(SECRET_KEY="s3cret"))
stub("django.core.signing", base64_hmac=base64_hmac)

from impl import check_signature  # noqa: E402

GOOD = base64_hmac("key1", "prod", "s3cret")[:8]


def test_valid_signature():
    assert check_signature("key1", "prod", GOOD)
    assert check_signature("key1", "prod", GOOD + "-2")  # only the first 8 characters count


def test_wrong_tag_key_or_signature():
    assert not check_signature("key1", "staging", GOOD)
    assert not check_signature("key2", "prod", GOOD)
    assert not check_signature("key1", "prod", "AAAAAAAA")
