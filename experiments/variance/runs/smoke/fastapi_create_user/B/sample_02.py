import re
from typing import Annotated, Callable

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

app = FastAPI()

# In-memory store standing in for a real database.
_USERS: dict[int, dict] = {}
_EMAIL_INDEX: dict[str, int] = {}


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    age: int | None = Field(default=None, ge=13, le=120)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_]+", value):
            raise ValueError("username may only contain letters, digits and underscores")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not (re.search(r"[A-Za-z]", value) and re.search(r"\d", value)):
            raise ValueError("password must contain at least one letter and one digit")
        return value


class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    age: int | None = None


def hash_password(password: str) -> str:
    import hashlib
    import os

    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return salt.hex() + ":" + digest.hex()


def save_user(user: UserCreate) -> dict:
    """Persist a user; raises ValueError if the email is already taken."""
    email_key = user.email.lower()
    if email_key in _EMAIL_INDEX:
        raise ValueError("email already registered")
    user_id = len(_USERS) + 1
    record = {
        "id": user_id,
        "username": user.username,
        "email": email_key,
        "age": user.age,
        "password_hash": hash_password(user.password),
    }
    _USERS[user_id] = record
    _EMAIL_INDEX[email_key] = user_id
    return record


def get_user_repo() -> Callable[[UserCreate], dict]:
    return save_user


@app.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    repo: Annotated[Callable[[UserCreate], dict], Depends(get_user_repo)],
) -> dict:
    try:
        return repo(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
