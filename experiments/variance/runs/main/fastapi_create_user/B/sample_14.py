import hashlib
import hmac
import os
import re
from typing import Awaitable, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

router = APIRouter()

# Repository function type: persists a user dict and returns the stored record.
# It should raise ValueError("duplicate") if the email/username already exists.
CreateUserFn = Callable[[dict], Awaitable[dict]]
FindUserFn = Callable[[str], Awaitable[Optional[dict]]]

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")


class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not USERNAME_RE.match(v):
            raise ValueError("Username may contain only letters, digits and underscores")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must contain at least one letter and one digit")
        return v


class SignupResponse(BaseModel):
    id: str
    username: str
    email: EmailStr


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$")
    candidate = hash_password(password, bytes.fromhex(salt_hex)).split("$")[1]
    return hmac.compare_digest(candidate, digest_hex)


def get_create_user() -> CreateUserFn:
    """Dependency provider. Override via app.dependency_overrides in the real app/tests."""
    raise NotImplementedError("Provide a create_user repository function")


def get_find_user_by_email() -> FindUserFn:
    """Dependency provider. Override via app.dependency_overrides in the real app/tests."""
    raise NotImplementedError("Provide a find_user_by_email repository function")


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    payload: SignupRequest,
    create_user: CreateUserFn = Depends(get_create_user),
    find_user_by_email: FindUserFn = Depends(get_find_user_by_email),
) -> SignupResponse:
    email = payload.email.lower()

    if await find_user_by_email(email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user_record = {
        "username": payload.username,
        "email": email,
        "password_hash": hash_password(payload.password),
    }

    try:
        stored = await create_user(user_record)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email or username already exists",
        )

    return SignupResponse(
        id=str(stored["id"]),
        username=stored["username"],
        email=stored["email"],
    )
