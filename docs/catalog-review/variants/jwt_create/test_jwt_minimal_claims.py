from datetime import datetime, timedelta, timezone

import pytest

jwt = pytest.importorskip("jwt")
from jwt_minimal_claims import create_access_token  # noqa: E402

SECRET = "s" * 32
NOW = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)


def decode(token, secret=SECRET, **kw):
    return jwt.decode(token, secret, algorithms=["HS256"], **kw)


def test_claims_and_expiry():
    token = create_access_token(42, SECRET, timedelta(minutes=5), now=NOW)
    claims = decode(token, options={"verify_exp": False, "verify_iat": False})
    assert claims == {"sub": "42", "iat": int(NOW.timestamp()),
                      "exp": int((NOW + timedelta(minutes=5)).timestamp())}
    assert jwt.get_unverified_header(token)["alg"] == "HS256"


def test_valid_now_decodes_with_real_clock():
    assert decode(create_access_token("u1", SECRET))["sub"] == "u1"


def test_expired_token_rejected():
    token = create_access_token("u1", SECRET, now=datetime.now(timezone.utc) - timedelta(hours=1))
    with pytest.raises(jwt.ExpiredSignatureError):
        decode(token)


def test_wrong_secret_rejected():
    with pytest.raises(jwt.InvalidSignatureError):
        decode(create_access_token("u1", SECRET), secret="x" * 32)


@pytest.mark.parametrize(
    "kwargs,message",
    [
        ({"user_id": ""}, "user_id"),
        ({"user_id": None}, "user_id"),
        ({"secret": "short"}, "at least 32 bytes"),
        ({"expires_in": timedelta(0)}, "positive"),
        ({"now": datetime(2030, 1, 1)}, "timezone-aware"),
    ],
)
def test_rejects_bad_input(kwargs, message):
    args = {"user_id": "u1", "secret": SECRET, **kwargs}
    with pytest.raises(ValueError, match=message):
        create_access_token(**args)
