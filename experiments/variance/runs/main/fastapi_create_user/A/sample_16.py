import re
from typing import Any, Awaitable, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

router = APIRouter()

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")

CreateUserFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip()
        if not USERNAME_PATTERN.match(value):
            raise ValueError(
                "username may only contain letters, digits, underscores, dots and hyphens"
            )
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_PATTERN.match(value):
            raise ValueError("invalid email address")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not (any(c.isalpha() for c in value) and any(c.isdigit() for c in value)):
            raise ValueError("password must contain at least one letter and one digit")
        return value


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None


def get_create_user_fn() -> CreateUserFn:
    """Dependency provider; override via app.dependency_overrides or replace with real wiring."""

    async def _not_configured(user_data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("create_user repository function is not configured")

    return _not_configured


def hash_password(password: str) -> str:
    """Hash the password before persistence (replace with bcrypt/argon2 in production)."""
    import hashlib
    import os

    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"{salt.hex()}${digest.hex()}"


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_endpoint(
    payload: UserCreate,
    create_user: CreateUserFn = Depends(get_create_user_fn),
) -> UserResponse:
    user_data = {
        "username": payload.username,
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "full_name": payload.full_name,
    }

    try:
        created = await create_user(user_data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc) or "user already exists",
        )
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="user service unavailable",
        )

    return UserResponse(
        id=created["id"],
        username=created["username"],
        email=created["email"],
        full_name=created.get("full_name"),
    )
