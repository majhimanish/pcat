import re
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

app = FastAPI()

# In-memory store standing in for a real database.
_USERS: dict[int, dict] = {}
_NEXT_ID = {"value": 1}

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    age: Optional[int] = Field(default=None, ge=13, le=120)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not USERNAME_RE.match(v):
            raise ValueError("username may contain only letters, digits and underscores")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
            raise ValueError("password must contain at least one letter and one digit")
        return v


class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    age: Optional[int] = None


def hash_password(password: str) -> str:
    import hashlib
    import os

    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return salt.hex() + ":" + digest.hex()


def save_user(user: dict) -> dict:
    """Repository function: persists a user and returns the stored record."""
    for existing in _USERS.values():
        if existing["username"].lower() == user["username"].lower():
            raise ValueError("username already exists")
        if existing["email"].lower() == user["email"].lower():
            raise ValueError("email already exists")
    user_id = _NEXT_ID["value"]
    _NEXT_ID["value"] += 1
    record = {"id": user_id, **user}
    _USERS[user_id] = record
    return record


def get_user_repo():
    """Dependency provider returning the persistence function."""
    return save_user


@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, repo=Depends(get_user_repo)):
    data = {
        "username": payload.username,
        "email": str(payload.email),
        "password_hash": hash_password(payload.password),
        "age": payload.age,
    }
    try:
        stored = repo(data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return stored
