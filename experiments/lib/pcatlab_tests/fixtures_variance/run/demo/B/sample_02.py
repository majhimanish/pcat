import os
from datetime import datetime, timedelta
from jose import jwt

SIGNING_KEY = os.environ.get("JWT_SECRET", "dev")


def create_access_token(user_id: int, expires_minutes: int = 30) -> str:
    to_encode = {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(minutes=expires_minutes)}
    return jwt.encode(to_encode, SIGNING_KEY, algorithm="HS256")


if __name__ == "__main__":
    print(create_access_token(1))
