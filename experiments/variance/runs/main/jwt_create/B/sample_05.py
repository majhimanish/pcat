import os
import time
import uuid
from typing import Optional

import jwt  # PyJWT

JWT_ALGORITHM = "HS256"
DEFAULT_TTL_SECONDS = 15 * 60


def create_access_token(
    user_id: str,
    secret_key: Optional[str] = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
    extra_claims: Optional[dict] = None,
) -> str:
    """Build and sign a JWT access token for the given user id.

    The signing key is read from the JWT_SECRET_KEY environment variable
    unless passed explicitly. Never hardcode secrets in source.
    """
    if not user_id:
        raise ValueError("user_id is required")
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")

    secret_key = secret_key or os.environ.get("JWT_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("JWT signing key is not configured (JWT_SECRET_KEY)")

    now = int(time.time())
    claims = dict(extra_claims or {})
    claims.update(
        {
            "sub": str(user_id),
            "iat": now,
            "nbf": now,
            "exp": now + ttl_seconds,
            "jti": uuid.uuid4().hex,
            "type": "access",
        }
    )
    if issuer:
        claims["iss"] = issuer
    if audience:
        claims["aud"] = audience

    return jwt.encode(claims, secret_key, algorithm=JWT_ALGORITHM)
