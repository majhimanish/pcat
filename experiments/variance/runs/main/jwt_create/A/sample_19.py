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
    """Create a signed JWT access token for a user id with an expiry time.

    The signing secret is read from the JWT_SECRET_KEY environment variable
    unless passed explicitly. It is never hard-coded.
    """
    if not user_id:
        raise ValueError("user_id must be a non-empty value")
    if expires_in_seconds <= 0:
        raise ValueError("expires_in_seconds must be positive")
    if algorithm not in ("HS256", "HS384", "HS512"):
        raise ValueError("Unsupported algorithm; use HS256, HS384 or HS512")

    secret = secret_key or os.environ.get("JWT_SECRET_KEY")
    if not secret or len(secret) < 32:
        raise RuntimeError(
            "A signing secret of at least 32 characters is required "
            "(set JWT_SECRET_KEY or pass secret_key)"
        )

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

    token = jwt.encode(payload, secret, algorithm=algorithm)
    return token if isinstance(token, str) else token.decode("utf-8")
