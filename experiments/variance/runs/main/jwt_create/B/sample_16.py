import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT


def generate_access_token(
    user_id: str,
    expires_in: int | timedelta = 3600,
    secret_key: str | None = None,
    algorithm: str = "HS256",
    issuer: str | None = None,
    audience: str | None = None,
    extra_claims: dict | None = None,
) -> str:
    """
    Generate a signed JWT access token for the given user ID.

    Args:
        user_id: Identifier of the user (stored in the "sub" claim).
        expires_in: Lifetime as seconds (int) or a timedelta. Default 1 hour.
        secret_key: Signing key. Defaults to the JWT_SECRET_KEY env variable.
        algorithm: Signing algorithm (default HS256).
        issuer: Optional "iss" claim.
        audience: Optional "aud" claim.
        extra_claims: Optional additional claims. Reserved claims
            (sub, iat, nbf, exp, jti, iss, aud) cannot be overridden.

    Returns:
        The encoded JWT as a string.

    Raises:
        ValueError: If user_id is empty, the key is missing, or the lifetime
            is not positive.
    """
    if not user_id:
        raise ValueError("user_id must be a non-empty value")

    secret_key = secret_key or os.environ.get("JWT_SECRET_KEY")
    if not secret_key:
        raise ValueError(
            "A signing key is required: pass secret_key or set JWT_SECRET_KEY"
        )

    lifetime = (
        expires_in
        if isinstance(expires_in, timedelta)
        else timedelta(seconds=expires_in)
    )
    if lifetime.total_seconds() <= 0:
        raise ValueError("expires_in must be positive")

    now = datetime.now(timezone.utc)
    payload = dict(extra_claims or {})
    payload.update(
        {
            "sub": str(user_id),
            "iat": now,
            "nbf": now,
            "exp": now + lifetime,
            "jti": uuid.uuid4().hex,
        }
    )
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience

    return jwt.encode(payload, secret_key, algorithm=algorithm)
