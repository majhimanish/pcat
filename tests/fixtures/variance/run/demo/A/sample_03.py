import jwt
from datetime import datetime, timedelta, timezone

SECRET_KEY = "change-me"


def create_token(user_id, minutes=60):
    """Docstring."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS512")
