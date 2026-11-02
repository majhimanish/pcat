import os
import time
import uuid

import jwt  # PyJWT


def generate_access_token(
    user_id: str,
    expires_in_seconds: int = 900,
    secret_key: str | None = None,
    algorithm: str = "HS256",
    issuer: str | None = None,
    audience: str | None = None,
    extra_claims: dict | None = None,
) -> str:
    """Generate a signed JWT access token for the given user ID.

    Args:
        user_id: Identifier placed in the "sub" claim.
        expires_in_seconds: Token lifetime in seconds (default 15 minutes).
        secret_key: Signing key. Falls back to the JWT_SECRET_KEY env var.
        algorithm: JWT signing algorithm (default HS256).
        issuer: Optional "iss" claim.
        audience: Optional "aud" claim.
        extra_claims: Optional additional claims (cannot override reserved ones).

    Returns:
        The encoded JWT as a string.

    Raises:
        ValueError: If inputs are invalid or no secret key is available.
    """
    if not user_id:
        raise ValueError("user_id must be a non-empty value")
    if expires_in_seconds <= 0:
        raise ValueError("expires_in_seconds must be positive")

    key = secret_key or os.environ.get("JWT_SECRET_KEY")
    if not key:
        raise ValueError(
            "A signing key must be provided via secret_key or JWT_SECRET_KEY"
        )

    now = int(time.time())
    payload = dict(extra_claims or {})
    payload.update(
        {
            "sub": str(user_id),
            "iat": now,
            "nbf": now,
            "exp": now + int(expires_in_seconds),
            "jti": uuid.uuid4().hex,
            "type": "access",
        }
    )
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience

    token = jwt.encode(payload, key, algorithm=algorithm)
    return token if isinstance(token, str) else token.decode("utf-8")
