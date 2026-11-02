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
    """Issue a signed JWT access token containing the user's id and an expiration."""
    secret_key = secret_key or os.environ.get("JWT_SECRET_KEY")
    if not secret_key:
        raise ValueError("A signing secret is required (pass secret_key or set JWT_SECRET_KEY).")
    if len(secret_key) < 32:
        raise ValueError("Signing secret must be at least 32 characters.")
    if user_id is None or str(user_id) == "":
        raise ValueError("user_id is required.")
    if expires_in_seconds <= 0:
        raise ValueError("expires_in_seconds must be positive.")
    if algorithm not in ("HS256", "HS384", "HS512"):
        raise ValueError("Unsupported algorithm.")

    now = int(time.time())
    claims = {
        "sub": str(user_id),
        "iat": now,
        "nbf": now,
        "exp": now + int(expires_in_seconds),
        "jti": uuid.uuid4().hex,
        "type": "access",
    }
    if issuer:
        claims["iss"] = issuer
    if audience:
        claims["aud"] = audience

    return jwt.encode(claims, secret_key, algorithm=algorithm)
