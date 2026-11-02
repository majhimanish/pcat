import hashlib
import hmac
import os
import re
from typing import Awaitable, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

router = APIRouter()

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
USERNAME_REGEX = re.compile(r"^[A-Za-z0-9_]{3,30}$")

# Repository function type: takes a user dict, returns the stored user dict.
# Raises ValueError if the email or username already exists.
CreateUserFn = Callable[[dict], Awaitable[dict]]


class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not USERNAME_REGEX.match(value):
            raise ValueError("Username may contain only letters, numbers and underscores")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_REGEX.match(value):
            raise ValueError("Invalid email address")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain a lowercase letter")
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain an uppercase letter")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain a digit")
        return value


class SignupResponse(BaseModel):
    id: str
    username: str
    email: str


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$")
    candidate = hash_password(password, bytes.fromhex(salt_hex)).split("$")[1]
    return hmac.compare_digest(candidate, digest_hex)


async def get_create_user_fn() -> CreateUserFn:
    """Dependency placeholder: override with app.dependency_overrides
    to inject the real repository function."""
    raise NotImplementedError("Repository function not configured")


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    payload: SignupRequest,
    create_user: CreateUserFn = Depends(get_create_user_fn),
) -> SignupResponse:
    user_record = {
        "username": payload.username,
        "email": payload.email,
        "password_hash": hash_password(payload.password),
    }

    try:
        saved = await create_user(user_record)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered",
        )

    return SignupResponse(
        id=str(saved["id"]),
        username=saved["username"],
        email=saved["email"],
    )
