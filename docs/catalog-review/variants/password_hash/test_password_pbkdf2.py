import hmac

import pytest

import password_pbkdf2 as mod

FAST = {"iterations": 1000}  # cheap parameters keep tests fast; verify reads them from the hash


def test_round_trip_and_wrong_password():
    stored = mod.hash_password("correct horse", **FAST)
    assert mod.verify_password("correct horse", stored)
    assert not mod.verify_password("correct horsf", stored)
    assert not mod.verify_password("", stored)


def test_default_parameters_are_strong_and_stored():
    stored = mod.hash_password("pw")
    assert stored.split("$")[1] == "600000"
    assert mod.verify_password("pw", stored)


def test_format_and_unique_salts():
    a, b = mod.hash_password("same", **FAST), mod.hash_password("same", **FAST)
    assert a != b
    parts = a.split("$")
    assert len(parts) == 4 and parts[:len(["pbkdf2_sha256", "1000"])] == ["pbkdf2_sha256", "1000"]


def test_unicode_passwords():
    stored = mod.hash_password("pässwörd ✓", **FAST)
    assert mod.verify_password("pässwörd ✓", stored) and not mod.verify_password("passwort", stored)


@pytest.mark.parametrize("stored", ["", "garbage", "md5$abc", "$$$$$", "scrypt$x$8$1$a$b",
                                    "pbkdf2_sha256$-5$AAAA$AAAA", "pbkdf2_sha256$99999999999$AAAA$AAAA",
                                    "scrypt$1024$8$999$AAAA$AAAA", "scrypt$1024$8$1$not-base64!$AAAA"])
def test_malformed_hashes_return_false(stored):
    assert mod.verify_password("pw", stored) is False


def test_tampered_parameters_fail():
    stored = mod.hash_password("pw", **FAST)
    assert not mod.verify_password("pw", stored.replace("$1000$", "$1001$", 1))


def test_uses_constant_time_compare(monkeypatch):
    calls = []
    real = hmac.compare_digest
    monkeypatch.setattr(mod.hmac, "compare_digest", lambda a, b: calls.append(1) or real(a, b))
    mod.verify_password("pw", mod.hash_password("pw", **FAST))
    assert calls == [1]
