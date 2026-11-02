import os
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT

JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15


def create_access_token(user_id, expires_minutes=ACCESS_TOKEN_EXPIRE_MINUTES):
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET environment variable is not set")
    if user_id is None or user_id == "":
        raise ValueError("user_id is required")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
