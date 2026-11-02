import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT


def generate_access_token(
    user_id: str,
    expires_in: timedelta | int = timedelta(minutes=15),
    secret_key: str | None = None,
    algorithm: str = "HS256",
    issuer: str | None = None,
    audience: str | None = None,
    extra_claims: dict | None = None,
) -> str:
    """
    Generate a signed JWT access token for the given user ID.

    Args:
        user_id: Unique identifier of the user (stored in the "sub" claim).
        expires_in: Token lifetime, as a timedelta or number of seconds.
        secret_key: Signing key. Defaults to the JWT_SECRET_KEY environment variable.
        algorithm: Signing algorithm (default HS256).
        issuer: Optional "iss" claim.
        audience: Optional "aud" claim.
        extra_claims: Optional additional claims. Registered claims
            (sub, iat, nbf, exp, jti, iss, aud) cannot be overridden.

    Returns:
        The encoded JWT as a string.

    Raises:
        ValueError: If user_id is empty, the lifetime is not positive,
            or no secret key is available.
    """
    if not user_id:
        raise ValueError("user_id must be a non-empty value")

    key = secret_key or os.environ.get("JWT_SECRET_KEY")
    if not key:
        raise ValueError(
            "A signing key is required: pass secret_key or set JWT_SECRET_KEY"
        )

    if isinstance(expires_in, (int, float)):
        expires_in = timedelta(seconds=expires_in)
    if expires_in.total_seconds() <= 0:
        raise ValueError("expires_in must be positive")

    now = datetime.now(timezone.utc)
    claims = dict(extra_claims or {})
    claims.update(
        {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + expires_in).timestamp()),
            "jti": uuid.uuid4().hex,
        }
    )
    if issuer:
        claims["iss"] = issuer
    if audience:
        claims["aud"] = audience

    return jwt.encode(claims, key, algorithm=algorithm)
