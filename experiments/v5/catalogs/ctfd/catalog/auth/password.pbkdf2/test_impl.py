import base64
import hashlib
import hmac

import pytest

import impl
from impl import hash_password, needs_rehash, verify_password


def legacy_hash(password, iterations, salt=b"0123456789abcdef"):
    """A hash in the same format made with fewer iterations (as before an upgrade)."""
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    b64 = base64.b64encode
    return f"pbkdf2_sha256${iterations}${b64(salt).decode()}${b64(key).decode()}"


@pytest.fixture(scope="module")
def stored():
    return hash_password("correct horse battery staple")


# Normal cases ---------------------------------------------------------------
def test_round_trip(stored):
    assert verify_password("correct horse battery staple", stored)


def test_format_and_default_iterations(stored):
    scheme, iterations, salt, key = stored.split("$")
    assert scheme == "pbkdf2_sha256" and iterations == "600000"
    assert len(base64.b64decode(salt)) == 16 and len(base64.b64decode(key)) == 32


def test_unicode_and_empty_passwords():
    for password in ("pässwörd ✓", ""):
        assert verify_password(password, hash_password(password))


# Security properties ------------------------------------------------------------
def test_wrong_password_rejected(stored):
    for attempt in ("correct horse battery stapl", "Correct horse battery staple", "", "x" * 1000):
        assert not verify_password(attempt, stored)


def test_salts_are_random():
    assert hash_password("same") != hash_password("same")


def test_never_hashes_below_owasp_minimum():
    with pytest.raises(ValueError, match="600000"):
        hash_password("pw", iterations=599999)
    with pytest.raises(ValueError):
        hash_password("pw", iterations=10000001)


def test_iteration_count_can_be_raised_later(stored):
    stronger = hash_password("pw", iterations=650000)
    assert stronger.split("$")[1] == "650000" and verify_password("pw", stronger)
    # Old hashes keep working and are flagged for upgrade once the target is raised.
    assert verify_password("correct horse battery staple", stored)
    assert not needs_rehash(stored) and needs_rehash(stored, iterations=650000)
    assert not needs_rehash(stronger, iterations=650000)


def test_legacy_low_iteration_hash_verifies_but_needs_rehash():
    old = legacy_hash("pw", 1000)
    assert verify_password("pw", old) and not verify_password("px", old)
    assert needs_rehash(old)


def test_tampered_hash_fails():
    old = legacy_hash("pw", 1000)
    assert not verify_password("pw", old.replace("$1000$", "$1001$"))
    scheme, it, salt, key = old.split("$")
    flipped = base64.b64encode(bytes([base64.b64decode(key)[0] ^ 1]) + base64.b64decode(key)[1:]).decode()
    assert not verify_password("pw", "$".join([scheme, it, salt, flipped]))


@pytest.mark.parametrize("stored", [
    "", "garbage", "md5$5f4dcc3b5aa765d61d8327deb882cf99", "$$$", "pbkdf2_sha256$x$AAAA$AAAA",
    "pbkdf2_sha256$0$AAAA$AAAA", "pbkdf2_sha256$-1$AAAA$AAAA", "pbkdf2_sha256$99999999999$AAAA$AAAA",
    "pbkdf2_sha1$1000$AAAA$AAAA", "pbkdf2_sha256$1000$not base64!$AAAA", "pbkdf2_sha256$1000$AAAA$AAAA$extra",
])
def test_malformed_or_foreign_hashes_return_false_and_need_rehash(stored):
    assert verify_password("pw", stored) is False
    assert needs_rehash(stored)


def test_comparison_is_constant_time(monkeypatch):
    calls = []
    real = hmac.compare_digest
    monkeypatch.setattr(impl.hmac, "compare_digest", lambda a, b: calls.append(1) or real(a, b))
    assert verify_password("pw", legacy_hash("pw", 1000))
    assert not verify_password("px", legacy_hash("pw", 1000))
    assert calls == [1, 1]


def test_no_md5_or_sha1(stored):
    source = open(impl.__file__).read().lower()
    assert "md5" not in source and "sha1" not in source.replace("pbkdf2_sha256", "")
