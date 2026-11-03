import uuid
from datetime import datetime, timedelta, timezone

import pytest

jwt = pytest.importorskip("jwt")
from impl import create_access_token  # noqa: E402

SECRET = "k" * 32
ISS, AUD = "auth.example", "orders-api"
FIXED = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
NO_TIME_CHECKS = {"verify_exp": False, "verify_nbf": False, "verify_iat": False}


def make(**kw):
    args = {"user_id": 42, "secret": SECRET, "issuer": ISS, "audience": AUD, **kw}
    return create_access_token(**args)


def decode(token, secret=SECRET, audience=AUD, issuer=ISS, **kw):
    return jwt.decode(token, secret, algorithms=["HS256"], audience=audience, issuer=issuer, **kw)


# Normal cases ---------------------------------------------------------------
def test_all_registered_claims_present():
    claims = decode(make(now=FIXED, expires_in=timedelta(minutes=5)), options=NO_TIME_CHECKS)
    ts = int(FIXED.timestamp())
    assert {k: claims[k] for k in ("sub", "iss", "aud", "iat", "nbf", "exp")} == {
        "sub": "42", "iss": ISS, "aud": AUD, "iat": ts, "nbf": ts, "exp": ts + 300}
    assert uuid.UUID(hex=claims["jti"])  # 128-bit random id


def test_default_lifetime_is_15_minutes_and_current_token_verifies():
    claims = decode(make())
    assert claims["exp"] - claims["iat"] == 15 * 60 and claims["sub"] == "42"


def test_string_user_ids_and_header():
    token = make(user_id="user-7")
    assert decode(token)["sub"] == "user-7"
    assert jwt.get_unverified_header(token) == {"alg": "HS256", "typ": "JWT"}


def test_non_utc_aware_clock_is_accepted():
    plus2 = timezone(timedelta(hours=2))
    claims = decode(make(now=FIXED.astimezone(plus2)), options=NO_TIME_CHECKS)
    assert claims["iat"] == int(FIXED.timestamp())


# Security properties ------------------------------------------------------------
def test_expired_token_rejected():
    with pytest.raises(jwt.ExpiredSignatureError):
        decode(make(now=datetime.now(timezone.utc) - timedelta(hours=1)))


def test_not_yet_valid_token_rejected():
    with pytest.raises(jwt.ImmatureSignatureError):
        decode(make(now=datetime.now(timezone.utc) + timedelta(hours=1)))


def test_wrong_secret_rejected():
    with pytest.raises(jwt.InvalidSignatureError):
        decode(make(), secret="x" * 32)


def test_token_for_another_audience_or_issuer_rejected():
    token = make()
    with pytest.raises(jwt.InvalidAudienceError):
        decode(token, audience="billing-api")
    with pytest.raises(jwt.InvalidIssuerError):
        decode(token, issuer="evil.example")


def test_tampered_payload_rejected():
    header, payload, signature = make().split(".")
    forged = jwt.encode({"sub": "admin", "iss": ISS, "aud": AUD}, "y" * 32, algorithm="HS256")
    with pytest.raises(jwt.InvalidSignatureError):
        decode(".".join([header, forged.split(".")[1], signature]))


def test_unsigned_alg_none_token_is_not_accepted_by_pinned_verifier():
    unsigned = jwt.encode({"sub": "42", "iss": ISS, "aud": AUD}, None, algorithm="none")
    with pytest.raises(jwt.InvalidAlgorithmError):
        decode(unsigned)


def test_token_ids_are_unique_and_secret_not_in_token():
    tokens = [make() for _ in range(20)]
    assert len({decode(t)["jti"] for t in tokens}) == 20
    assert all(SECRET not in t for t in tokens)


# Failure cases --------------------------------------------------------------------
@pytest.mark.parametrize(
    "kw,message",
    [
        ({"user_id": ""}, "user_id"),
        ({"user_id": None}, "user_id"),
        ({"issuer": ""}, "issuer"),
        ({"audience": ""}, "audience"),
        ({"secret": "k" * 31}, "at least 32 bytes"),
        ({"expires_in": timedelta(0)}, "positive"),
        ({"expires_in": timedelta(seconds=-5)}, "positive"),
        ({"now": datetime(2030, 1, 1)}, "timezone-aware"),
    ],
)
def test_rejects_bad_input(kw, message):
    with pytest.raises(ValueError, match=message):
        make(**kw)


def test_secret_length_counts_bytes_not_characters():
    assert decode(make(secret="é" * 16), secret="é" * 16)["sub"] == "42"  # 16 chars, 32 bytes
