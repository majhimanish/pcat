import os
import time
import uuid

import jwt  # PyJWT


def issue_access_token(
    user_id,
    secret_key=None,
    expires_in_seconds=900,
    algorithm="HS256",
    issuer=None,
    audience=None,
):
    """Issue a signed JWT access token containing the user's id and an expiration.

    The signing key is read from the JWT_SECRET_KEY environment variable
    unless `secret_key` is passed explicitly.
    """
    if user_id is None or user_id == "":
        raise ValueError("user_id is required")
    if not isinstance(expires_in_seconds, int) or expires_in_seconds <= 0:
        raise ValueError("expires_in_seconds must be a positive integer")
    if algorithm not in ("HS256", "HS384", "HS512"):
        raise ValueError("unsupported algorithm for a shared secret key")

    key = secret_key or os.environ.get("JWT_SECRET_KEY")
    if not key:
        raise RuntimeError("No signing key: set JWT_SECRET_KEY or pass secret_key")
    if len(key) < 32:
        raise ValueError("Signing key must be at least 32 characters")

    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "iat": now,
        "nbf": now,
        "exp": now + expires_in_seconds,
        "jti": uuid.uuid4().hex,
    }
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience

    return jwt.encode(payload, key, algorithm=algorithm)
