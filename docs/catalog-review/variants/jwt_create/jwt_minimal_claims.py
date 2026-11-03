"""Signed JWT access token with minimal claims: sub, iat, exp.

Requires: pyjwt>=2.8,<3. HS256 with a caller-supplied secret.
"""

from datetime import datetime, timedelta, timezone

import jwt

ALGORITHM = "HS256"
MIN_SECRET_BYTES = 32  # RFC 7518: an HS256 key must be at least 256 bits


def create_access_token(
    user_id: str | int,
    secret: str,
    expires_in: timedelta = timedelta(minutes=15),
    now: datetime | None = None,
) -> str:
    """Return a signed HS256 JWT for `user_id` that expires after `expires_in`."""
    if user_id is None or str(user_id) == "":
        raise ValueError("user_id is required")
    if len(secret.encode("utf-8")) < MIN_SECRET_BYTES:
        raise ValueError(f"secret must be at least {MIN_SECRET_BYTES} bytes")
    if expires_in <= timedelta(0):
        raise ValueError("expires_in must be positive")
    issued_at = now or datetime.now(timezone.utc)
    if issued_at.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    payload = {"sub": str(user_id), "iat": issued_at, "exp": issued_at + expires_in}
    return jwt.encode(payload, secret, algorithm=ALGORITHM)
