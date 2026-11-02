import re
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

app = FastAPI()

# In-memory store standing in for a real database.
_USERS: dict[str, dict[str, Any]] = {}

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,32}$")


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    age: int | None = Field(default=None, ge=13, le=120)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not USERNAME_PATTERN.match(value):
            raise ValueError("username may only contain letters, digits and underscores")
        return value.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not (re.search(r"[a-z]", value) and re.search(r"[A-Z]", value) and re.search(r"\d", value)):
            raise ValueError("password must contain lowercase, uppercase and a digit")
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


def create_user_in_store(user: UserCreate) -> dict[str, Any]:
    """Persist a user; raises ValueError on duplicate username/email."""
    for existing in _USERS.values():
        if existing["username"] == user.username:
            raise ValueError("username already exists")
        if existing["email"].lower() == user.email.lower():
            raise ValueError("email already exists")

    user_id = len(_USERS) + 1
    record = {
        "id": user_id,
        "username": user.username,
        "email": user.email,
        "age": user.age,
        "password_hash": hash_password(user.password),
    }
    _USERS[user.username] = record
    return record


def get_create_user_repo():
    """Dependency provider returning the persistence function."""
    return create_user_in_store


@app.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    payload: UserCreate,
    create_user: Annotated[Any, Depends(get_create_user_repo)],
) -> UserRead:
    try:
        record = create_user(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return UserRead(**{k: v for k, v in record.items() if k != "password_hash"})
