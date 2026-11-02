import os
import time
import jwt  # PyJWT


def issue_access_token(
    user_id,
    secret_key=None,
    expires_in_seconds=900,
    algorithm="HS256",
    issuer=None,
    audience=None,
):
    """Issue a signed JWT access token containing the user's id and an expiration.

    The signing secret is read from the JWT_SECRET_KEY environment variable
    unless passed explicitly. Never hard-code the secret in source.
    """
    secret_key = secret_key or os.environ.get("JWT_SECRET_KEY")
    if not secret_key:
        raise ValueError("A signing secret is required (set JWT_SECRET_KEY).")
    if user_id is None or user_id == "":
        raise ValueError("user_id is required.")
    if expires_in_seconds <= 0:
        raise ValueError("expires_in_seconds must be positive.")
    if algorithm.lower() == "none":
        raise ValueError("Unsigned tokens are not allowed.")

    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + int(expires_in_seconds),
    }
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience

    return jwt.encode(payload, secret_key, algorithm=algorithm)
