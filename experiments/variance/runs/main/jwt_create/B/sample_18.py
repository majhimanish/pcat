import os
import time

import jwt  # PyJWT


def mint_jwt(
    user_id: str,
    secret_key: str | None = None,
    expires_in_seconds: int = 3600,
    algorithm: str = "HS256",
) -> str:
    """Create a signed JWT containing the user id and an expiry."""
    secret_key = secret_key or os.environ.get("JWT_SECRET_KEY")
    if not secret_key:
        raise ValueError("A secret key must be provided or set in JWT_SECRET_KEY")

    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def verify_jwt(
    token: str,
    secret_key: str | None = None,
    algorithm: str = "HS256",
) -> dict:
    """Validate a token's signature and expiry, returning its claims."""
    secret_key = secret_key or os.environ.get("JWT_SECRET_KEY")
    if not secret_key:
        raise ValueError("A secret key must be provided or set in JWT_SECRET_KEY")

    return jwt.decode(token, secret_key, algorithms=[algorithm])
