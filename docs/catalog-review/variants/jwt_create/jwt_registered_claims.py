"""Signed JWT access token with the registered claims iss, aud, nbf and jti.

Requires: pyjwt>=2.8,<3. HS256 with a caller-supplied secret.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt

ALGORITHM = "HS256"
MIN_SECRET_BYTES = 32  # RFC 7518: an HS256 key must be at least 256 bits


def create_access_token(
    user_id: str | int,
    secret: str,
    issuer: str,
    audience: str,
    expires_in: timedelta = timedelta(minutes=15),
    now: datetime | None = None,
) -> str:
    """Return a signed HS256 JWT for `user_id`, bound to `issuer` and `audience`."""
    if user_id is None or str(user_id) == "":
        raise ValueError("user_id is required")
    if not issuer or not audience:
        raise ValueError("issuer and audience are required")
    if len(secret.encode("utf-8")) < MIN_SECRET_BYTES:
        raise ValueError(f"secret must be at least {MIN_SECRET_BYTES} bytes")
    if expires_in <= timedelta(0):
        raise ValueError("expires_in must be positive")
    issued_at = now or datetime.now(timezone.utc)
    if issued_at.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    payload = {
        "sub": str(user_id), "iss": issuer, "aud": audience,
        "iat": issued_at, "nbf": issued_at, "exp": issued_at + expires_in,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)
