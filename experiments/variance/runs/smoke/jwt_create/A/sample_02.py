import time
import uuid

import jwt  # PyJWT


def create_access_token(
    user_id: str,
    secret_key: str,
    expires_in_seconds: int = 900,
    algorithm: str = "HS256",
    issuer: str | None = None,
    audience: str | None = None,
) -> str:
    """Create a signed JWT access token for the given user id."""
    if not user_id:
        raise ValueError("user_id must be provided")
    if not secret_key:
        raise ValueError("secret_key must be provided")
    if expires_in_seconds <= 0:
        raise ValueError("expires_in_seconds must be positive")
    if algorithm.lower() == "none":
        raise ValueError("The 'none' algorithm is not allowed")

    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "iat": now,
        "nbf": now,
        "exp": now + expires_in_seconds,
        "jti": uuid.uuid4().hex,
        "type": "access",
    }
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience

    return jwt.encode(payload, secret_key, algorithm=algorithm)
