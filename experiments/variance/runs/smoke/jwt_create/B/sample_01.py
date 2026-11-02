import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT


def generate_access_token(
    user_id,
    expires_in_seconds=3600,
    secret_key=None,
    algorithm="HS256",
    issuer=None,
    audience=None,
    extra_claims=None,
):
    """
    Generate a signed JWT access token for the given user ID.

    Args:
        user_id: Identifier for the user (stored in the "sub" claim).
        expires_in_seconds: Token lifetime in seconds (configurable, default 1 hour).
        secret_key: Signing key. Falls back to the JWT_SECRET_KEY environment variable.
        algorithm: Signing algorithm (default HS256).
        issuer: Optional "iss" claim.
        audience: Optional "aud" claim.
        extra_claims: Optional dict of additional claims (cannot override reserved claims).

    Returns:
        The encoded JWT as a string.

    Raises:
        ValueError: If inputs are invalid or no signing key is available.
    """
    if user_id is None or str(user_id).strip() == "":
        raise ValueError("user_id must be a non-empty value")

    if not isinstance(expires_in_seconds, (int, float)) or isinstance(expires_in_seconds, bool):
        raise ValueError("expires_in_seconds must be a number")
    if expires_in_seconds <= 0:
        raise ValueError("expires_in_seconds must be positive")

    key = secret_key or os.environ.get("JWT_SECRET_KEY")
    if not key:
        raise ValueError(
            "A signing key is required: pass secret_key or set JWT_SECRET_KEY"
        )

    now = datetime.now(timezone.utc)
    payload = {}

    if extra_claims:
        payload.update(extra_claims)

    payload.update(
        {
            "sub": str(user_id),
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(seconds=expires_in_seconds),
            "jti": uuid.uuid4().hex,
            "type": "access",
        }
    )

    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience

    token = jwt.encode(payload, key, algorithm=algorithm)
    # PyJWT < 2.0 returns bytes; normalize to str
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token
