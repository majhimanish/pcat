import time
import uuid
from datetime import timedelta

import jwt  # PyJWT


def create_access_token(
    user_id: str,
    secret_key: str,
    expires_in: timedelta = timedelta(minutes=15),
    algorithm: str = "HS256",
    issuer: str | None = None,
    audience: str | None = None,
) -> str:
    """Create a signed JWT access token for a user id with an expiry time."""
    if not user_id:
        raise ValueError("user_id must not be empty")
    if not secret_key:
        raise ValueError("secret_key must not be empty")
    if expires_in.total_seconds() <= 0:
        raise ValueError("expires_in must be positive")
    if algorithm.lower() == "none":
        raise ValueError("unsigned tokens are not allowed")

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

    return jwt.encode(payload, secret_key, algorithm=algorithm)
