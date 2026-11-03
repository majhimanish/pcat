from datetime import datetime, timedelta, timezone

import pytest

jwt = pytest.importorskip("jwt")
from jwt_registered_claims import create_access_token  # noqa: E402

SECRET = "s" * 32
NOW = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)


def make(**kw):
    args = {"user_id": 7, "secret": SECRET, "issuer": "auth.example", "audience": "api", **kw}
    return create_access_token(**args)


def decode(token, **kw):
    kw.setdefault("audience", "api")
    kw.setdefault("issuer", "auth.example")
    return jwt.decode(token, SECRET, algorithms=["HS256"], **kw)


def test_registered_claims():
    claims = decode(make(now=NOW), options={"verify_exp": False, "verify_nbf": False, "verify_iat": False})
    ts = int(NOW.timestamp())
    assert {k: claims[k] for k in ("sub", "iss", "aud", "iat", "nbf")} == {
        "sub": "7", "iss": "auth.example", "aud": "api", "iat": ts, "nbf": ts}
    assert claims["exp"] == ts + 15 * 60 and len(claims["jti"]) == 32


def test_token_ids_are_unique():
    a, b = (decode(make())["jti"] for _ in range(2))
    assert a != b


def test_wrong_audience_or_issuer_rejected():
    token = make()
    with pytest.raises(jwt.InvalidAudienceError):
        decode(token, audience="other-api")
    with pytest.raises(jwt.InvalidIssuerError):
        decode(token, issuer="evil.example")


def test_expired_and_not_yet_valid_rejected():
    with pytest.raises(jwt.ExpiredSignatureError):
        decode(make(now=datetime.now(timezone.utc) - timedelta(hours=1)))
    with pytest.raises(jwt.ImmatureSignatureError):
        decode(make(now=datetime.now(timezone.utc) + timedelta(hours=1)))


def test_wrong_secret_rejected():
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(make(), "x" * 32, algorithms=["HS256"], audience="api")


@pytest.mark.parametrize(
    "kwargs,message",
    [({"issuer": ""}, "issuer"), ({"audience": ""}, "audience"), ({"secret": "k"}, "32 bytes"),
     ({"user_id": ""}, "user_id"), ({"expires_in": timedelta(seconds=-1)}, "positive"),
     ({"now": datetime(2030, 1, 1)}, "timezone-aware")],
)
def test_rejects_bad_input(kwargs, message):
    with pytest.raises(ValueError, match=message):
        make(**kwargs)
