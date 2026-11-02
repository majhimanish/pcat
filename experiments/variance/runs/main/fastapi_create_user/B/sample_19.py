import re
from typing import Callable, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

app = FastAPI()

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,30}$")


class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not USERNAME_PATTERN.match(value):
            raise ValueError("Username may contain only letters, numbers, and underscores")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain an uppercase letter")
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain a lowercase letter")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain a digit")
        return value


class SignupResponse(BaseModel):
    id: str
    username: str
    email: EmailStr


def hash_password(password: str) -> str:
    import hashlib
    import os

    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return salt.hex() + ":" + digest.hex()


def get_create_user() -> Callable[..., Optional[dict]]:
    """Dependency placeholder: override with app.dependency_overrides to
    provide a function create_user(username, email, password_hash) that
    returns the stored user dict, or None if username/email already exists."""
    raise NotImplementedError("create_user repository function not configured")


@app.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup(
    payload: SignupRequest,
    create_user: Callable[..., Optional[dict]] = Depends(get_create_user),
) -> SignupResponse:
    user = create_user(
        username=payload.username,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered",
        )
    return SignupResponse(
        id=str(user["id"]),
        username=user["username"],
        email=user["email"],
    )
