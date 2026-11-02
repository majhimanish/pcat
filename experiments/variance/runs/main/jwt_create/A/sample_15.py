import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt  # pip install PyJWT


def create_access_token(
    user_id: str,
    expires_in_minutes: int = 15,
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
        raise ValueError("A signing secret is required (set JWT_SECRET_KEY).")
    if not user_id:
        raise ValueError("user_id must not be empty.")
    if expires_in_minutes <= 0:
        raise ValueError("expires_in_minutes must be positive.")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=expires_in_minutes),
        "jti": uuid.uuid4().hex,
        "type": "access",
    }
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience

    return jwt.encode(payload, secret, algorithm=algorithm)
