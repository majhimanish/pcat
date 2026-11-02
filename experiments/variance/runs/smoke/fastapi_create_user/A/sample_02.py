import re
from typing import Awaitable, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

router = APIRouter()

CreateUserFn = Callable[[str, str, str], Awaitable[dict]]
FindUserByEmailFn = Callable[[str], Awaitable[Optional[dict]]]
HashPasswordFn = Callable[[str], str]


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            raise ValueError(
                "Username may only contain letters, digits, '_', '.', and '-'"
            )
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not (
            re.search(r"[a-z]", value)
            and re.search(r"[A-Z]", value)
            and re.search(r"\d", value)
        ):
            raise ValueError(
                "Password must contain lowercase, uppercase, and a digit"
            )
        return value


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr


def get_create_user() -> CreateUserFn:
    """Dependency provider; override in app setup or tests."""
    raise NotImplementedError("create_user repository function not configured")


def get_find_user_by_email() -> FindUserByEmailFn:
    """Dependency provider; override in app setup or tests."""
    raise NotImplementedError("find_user_by_email function not configured")


def get_hash_password() -> HashPasswordFn:
    """Dependency provider; override in app setup or tests."""
    raise NotImplementedError("hash_password function not configured")


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_endpoint(
    payload: UserCreateRequest,
    create_user: CreateUserFn = Depends(get_create_user),
    find_user_by_email: FindUserByEmailFn = Depends(get_find_user_by_email),
    hash_password: HashPasswordFn = Depends(get_hash_password),
) -> UserResponse:
    email = payload.email.lower()

    existing = await find_user_by_email(email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    password_hash = hash_password(payload.password)

    try:
        created = await create_user(payload.username, email, password_hash)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return UserResponse(
        id=created["id"],
        username=created["username"],
        email=created["email"],
    )
