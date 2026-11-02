import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt  # pip install PyJWT


def create_access_token(
    user_id: str,
    secret_key: str,
    expires_in_seconds: int = 900,
    algorithm: str = "HS256",
    issuer: str | None = None,
    audience: str | None = None,
) -> str:
    """Create a signed JWT access token for a user id with an expiry time."""
    if not user_id:
        raise ValueError("user_id is required")
    if not secret_key:
        raise ValueError("secret_key is required")
    if expires_in_seconds <= 0:
        raise ValueError("expires_in_seconds must be positive")
    if algorithm.lower() == "none":
        raise ValueError("Unsigned tokens are not allowed")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=expires_in_seconds),
        "jti": uuid.uuid4().hex,
        "type": "access",
    }
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience

    return jwt.encode(payload, secret_key, algorithm=algorithm)
