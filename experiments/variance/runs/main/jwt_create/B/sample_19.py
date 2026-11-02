import os
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15


def _get_secret_key() -> str:
    secret = os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY environment variable is not set")
    return secret


def create_access_token(user_id, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    """Return a signed JWT for user_id that expires after `expires_minutes` minutes."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=JWT_ALGORITHM)
