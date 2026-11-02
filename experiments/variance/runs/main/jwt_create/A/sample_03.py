import datetime
import os
import uuid

import jwt  # PyJWT


def create_access_token(
    user_id: str,
    expires_in_seconds: int = 900,
    secret_key: str | None = None,
    algorithm: str = "HS256",
    issuer: str | None = None,
    audience: str | None = None,
) -> str:
    """Create a signed JWT access token for the given user id.

    The signing secret is read from the JWT_SECRET_KEY environment variable
    unless passed explicitly. Never hard-code the secret in source code.
    """
    if not user_id:
        raise ValueError("user_id must be a non-empty value")
    if expires_in_seconds <= 0:
        raise ValueError("expires_in_seconds must be positive")

    secret = secret_key or os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "No signing key provided: pass secret_key or set JWT_SECRET_KEY"
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "nbf": now,
        "exp": now + datetime.timedelta(seconds=expires_in_seconds),
        "jti": uuid.uuid4().hex,
        "type": "access",
    }
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience

    token = jwt.encode(payload, secret, algorithm=algorithm)
    return token if isinstance(token, str) else token.decode("utf-8")
