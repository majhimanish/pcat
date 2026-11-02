import os
import time
import jwt  # PyJWT


def get_secret_key() -> str:
    """Load the signing secret from the environment (never hardcode it)."""
    secret = os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY environment variable is not set")
    return secret


def mint_jwt(user_id: str, expires_in_seconds: int = 3600, secret_key: str | None = None) -> str:
    """
    Create a signed JWT for a user.

    Claims:
      sub - the user id
      iat - issued-at (unix timestamp)
      exp - expiry (unix timestamp)
    """
    if not user_id:
        raise ValueError("user_id is required")
    if expires_in_seconds <= 0:
        raise ValueError("expires_in_seconds must be positive")

    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    key = secret_key or get_secret_key()
    return jwt.encode(payload, key, algorithm="HS256")


def verify_jwt(token: str, secret_key: str | None = None) -> dict:
    """Decode and validate a token; raises jwt.InvalidTokenError on failure."""
    key = secret_key or get_secret_key()
    return jwt.decode(
        token,
        key,
        algorithms=["HS256"],
        options={"require": ["sub", "exp", "iat"]},
    )
