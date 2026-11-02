from typing import Callable, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

app = FastAPI()

# In-memory store used by the default repository implementation.
_USERS: dict[int, dict] = {}


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    age: Optional[int] = Field(default=None, ge=13, le=120)

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, value: str) -> str:
        if not any(c.isdigit() for c in value) or not any(c.isalpha() for c in value):
            raise ValueError("Password must contain at least one letter and one digit")
        return value


class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    age: Optional[int] = None


def save_user_in_memory(user_data: dict) -> dict:
    """Default repository function: persists a user and returns the stored record."""
    for existing in _USERS.values():
        if existing["username"] == user_data["username"] or existing["email"] == user_data["email"]:
            raise ValueError("User with this username or email already exists")
    new_id = len(_USERS) + 1
    record = {"id": new_id, **user_data}
    _USERS[new_id] = record
    return record


def get_save_user() -> Callable[[dict], dict]:
    """Dependency provider; override in tests or swap for a real DB-backed function."""
    return save_user_in_memory


def hash_password(password: str) -> str:
    import hashlib
    import os

    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + ":" + digest.hex()


@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    save_user: Callable[[dict], dict] = Depends(get_save_user),
) -> UserOut:
    user_data = {
        "username": payload.username,
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "age": payload.age,
    }
    try:
        saved = save_user(user_data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return UserOut(**saved)
