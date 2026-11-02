import os
import time
import uuid
from datetime import timedelta

import jwt  # PyJWT


def create_access_token(
    user_id: str,
    expires_in: timedelta = timedelta(minutes=15),
    secret_key: str | None = None,
    algorithm: str = "HS256",
    issuer: str | None = None,
    audience: str | None = None,
) -> str:
    """Create a signed JWT access token for the given user id.

    The signing secret is read from the JWT_SECRET_KEY environment variable
    unless passed explicitly. Never hard-code the secret in source code.
    """
    secret = secret_key or os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise ValueError("A signing secret is required (JWT_SECRET_KEY).")
    if not user_id:
        raise ValueError("user_id must be a non-empty value.")
    if expires_in.total_seconds() <= 0:
        raise ValueError("expires_in must be a positive duration.")
    if algorithm.lower() == "none":
        raise ValueError("Unsigned tokens are not allowed.")

    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "iat": now,
        "nbf": now,
        "exp": now + int(expires_in.total_seconds()),
        "jti": uuid.uuid4().hex,
        "type": "access",
    }
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience

    return jwt.encode(payload, secret, algorithm=algorithm)
