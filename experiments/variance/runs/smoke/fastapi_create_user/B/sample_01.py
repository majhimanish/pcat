from typing import Callable, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

app = FastAPI()


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if not any(c.isdigit() for c in value) or not any(c.isalpha() for c in value):
            raise ValueError("Password must contain at least one letter and one digit")
        return value


class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    full_name: Optional[str] = None


def hash_password(password: str) -> str:
    import hashlib
    import os

    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return salt.hex() + ":" + digest.hex()


def save_user_in_db(user_data: dict) -> dict:
    """Placeholder repository implementation; replace with a real DB call.

    Should raise ValueError if the username or email already exists.
    """
    return {"id": 1, **user_data}


def get_save_user() -> Callable[[dict], dict]:
    """Dependency provider returning the repository function."""
    return save_user_in_db


@app.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    save_user: Callable[[dict], dict] = Depends(get_save_user),
) -> dict:
    user_data = {
        "username": payload.username,
        "email": str(payload.email),
        "full_name": payload.full_name,
        "password_hash": hash_password(payload.password),
    }
    try:
        saved = save_user(user_data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return saved
