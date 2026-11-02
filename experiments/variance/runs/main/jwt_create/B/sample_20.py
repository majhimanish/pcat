import os
import time
import uuid

import jwt  # PyJWT


def build_access_token_claims(
    user_id: str,
    issuer: str,
    audience: str,
    ttl_seconds: int = 900,
    now: int | None = None,
) -> dict:
    """Build the claim set for an access token."""
    if not user_id:
        raise ValueError("user_id is required")
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")

    issued_at = int(now if now is not None else time.time())
    return {
        "sub": str(user_id),
        "iss": issuer,
        "aud": audience,
        "iat": issued_at,
        "nbf": issued_at,
        "exp": issued_at + ttl_seconds,
        "jti": uuid.uuid4().hex,
        "type": "access",
    }


def create_access_token(
    user_id: str,
    secret: str | None = None,
    issuer: str = "auth-service",
    audience: str = "api",
    ttl_seconds: int = 900,
    algorithm: str = "HS256",
) -> str:
    """Build and sign a JWT access token for the given user id.

    The signing secret is read from the JWT_SECRET environment variable
    unless passed explicitly. Never hard-code it in source.
    """
    key = secret or os.environ.get("JWT_SECRET")
    if not key:
        raise RuntimeError("JWT signing secret is not configured (set JWT_SECRET)")
    if algorithm not in {"HS256", "HS384", "HS512"}:
        raise ValueError("unsupported algorithm for a shared secret")

    claims = build_access_token_claims(user_id, issuer, audience, ttl_seconds)
    return jwt.encode(claims, key, algorithm=algorithm)
