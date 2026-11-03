import os
import time
import uuid

import jwt  # PyJWT


def generate_access_token(
    user_id: str,
    secret_key: str | None = None,
    expires_in_seconds: int = 900,
    algorithm: str = "HS256",
    issuer: str | None = None,
    audience: str | None = None,
    extra_claims: dict | None = None,
) -> str:
    """Generate a signed JWT access token for the given user ID.

    Args:
        user_id: Identifier stored in the "sub" claim.
        secret_key: Signing key. Defaults to the JWT_SECRET_KEY environment variable.
        expires_in_seconds: Token lifetime in seconds (default 15 minutes).
        algorithm: Signing algorithm (default HS256).
        issuer: Optional "iss" claim.
        audience: Optional "aud" claim.
        extra_claims: Optional additional claims (cannot override reserved claims).

    Returns:
        The encoded JWT as a string.
    """
    if not user_id:
        raise ValueError("user_id must be a non-empty value")
    if expires_in_seconds <= 0:
        raise ValueError("expires_in_seconds must be positive")

    secret_key = secret_key or os.environ.get("JWT_SECRET_KEY")
    if not secret_key:
        raise ValueError(
            "A signing key is required: pass secret_key or set JWT_SECRET_KEY"
        )

    reserved_claims = {"sub", "iat", "nbf", "exp", "jti", "type", "iss", "aud"}
    payload = {
        key: value
        for key, value in (extra_claims or {}).items()
        if key not in reserved_claims
    }

    now = int(time.time())
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

    return jwt.encode(payload, secret_key, algorithm=algorithm)
