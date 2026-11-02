import re
from typing import Annotated, Callable

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

app = FastAPI()

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,30}$")


class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(..., min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    age: int | None = Field(default=None, ge=13, le=120)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not USERNAME_PATTERN.match(value):
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


_FAKE_DB: dict[int, dict] = {}


def hash_password(password: str) -> str:
    import hashlib
    import os

    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return salt.hex() + ":" + digest.hex()


def save_user_to_db(user: UserCreate) -> dict:
    """Persist a user. Raises ValueError if username or email already exists."""
    for existing in _FAKE_DB.values():
        if existing["username"].lower() == user.username.lower():
            raise ValueError("username already taken")
        if existing["email"].lower() == user.email.lower():
            raise ValueError("email already registered")

    user_id = len(_FAKE_DB) + 1
    record = {
        "id": user_id,
        "username": user.username,
        "email": user.email,
        "age": user.age,
        "password_hash": hash_password(user.password),
    }
    _FAKE_DB[user_id] = record
    return record


def get_user_repo() -> Callable[[UserCreate], dict]:
    return save_user_to_db


@app.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    save_user: Annotated[Callable[[UserCreate], dict], Depends(get_user_repo)],
) -> dict:
    try:
        return save_user(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
