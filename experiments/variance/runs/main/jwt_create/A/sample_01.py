import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT


def create_access_token(
    user_id: str,
    expires_in_seconds: int = 900,
    secret_key: str | None = None,
    algorithm: str = "HS256",
    issuer: str | None = None,
    audience: str | None = None,
) -> str:
    """Create a signed JWT access token for a user id with an expiry time."""
    secret = secret_key or os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise ValueError("A signing secret must be provided via secret_key or JWT_SECRET_KEY.")
    if not user_id:
        raise ValueError("user_id must not be empty.")
    if expires_in_seconds <= 0:
        raise ValueError("expires_in_seconds must be positive.")
    if algorithm.lower() == "none":
        raise ValueError("Unsigned tokens are not allowed.")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
        "jti": uuid.uuid4().hex,
        "type": "access",
    }
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience

    return jwt.encode(payload, secret, algorithm=algorithm)
