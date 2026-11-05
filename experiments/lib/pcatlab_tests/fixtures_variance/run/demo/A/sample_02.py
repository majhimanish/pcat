from datetime import datetime, timedelta, timezone
import jwt

KEY = "change-me"

def make_jwt(uid, minutes=15):
    # renamed, comments, same structure
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    claims = {"sub": str(uid), "exp": exp}
    return jwt.encode(claims, KEY, algorithm="HS256")
