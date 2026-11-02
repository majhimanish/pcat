from typing import Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, ConfigDict

app = FastAPI()


class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    full_name: Optional[str] = Field(default=None, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)


class UserRead(BaseModel):
    id: str
    username: str
    email: EmailStr
    full_name: Optional[str] = None


_USERS: dict[str, dict] = {}


def hash_password(password: str) -> str:
    import hashlib
    import os

    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return salt.hex() + ":" + digest.hex()


def create_user_in_db(payload: UserCreate) -> dict:
    for existing in _USERS.values():
        if existing["username"] == payload.username or existing["email"] == payload.email:
            raise ValueError("duplicate")
    user = {
        "id": str(uuid4()),
        "username": payload.username,
        "email": payload.email,
        "full_name": payload.full_name,
        "password_hash": hash_password(payload.password),
    }
    _USERS[user["id"]] = user
    return user


def get_create_user():
    return create_user_in_db


@app.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, create_user_fn=Depends(get_create_user)) -> UserRead:
    try:
        user = create_user_fn(payload)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )
    return UserRead(**user)
