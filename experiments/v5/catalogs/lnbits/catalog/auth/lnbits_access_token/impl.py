from datetime import datetime, timedelta, timezone
import jwt
from lnbits.settings import settings


def create_access_token(data: dict, token_expire_minutes: int | None = None) -> str:
    minutes = token_expire_minutes or settings.auth_token_expire_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    to_encode = {k: v for k, v in data.items() if v is not None}
    to_encode.update({"exp": expire})  # todo:check expiration
    return jwt.encode(to_encode, settings.auth_secret_key, "HS256")
