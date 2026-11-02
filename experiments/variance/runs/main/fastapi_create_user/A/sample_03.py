import re
from typing import Awaitable, Callable, Optional

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip()
        if not USERNAME_PATTERN.fullmatch(value):
            raise ValueError(
                "username may contain only letters, digits, '_', '.', '-'"
            )
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not (re.search(r"[A-Za-z]", value) and re.search(r"\d", value)):
            raise ValueError("password must contain letters and digits")
        return value


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    full_name: Optional[str] = None


CreateUserFn = Callable[[dict], Awaitable[dict]]


async def get_create_user_fn() -> CreateUserFn:
    """Dependency provider; override via app.dependency_overrides in
    production/tests to supply the real repository function."""
    raise NotImplementedError("create_user repository function not configured")


async def create_user_endpoint(
    payload: UserCreateRequest,
    create_user: CreateUserFn = Depends(get_create_user_fn),
) -> UserResponse:
    """POST /users handler (register with router.post('/users', status_code=201,
    response_model=UserResponse))."""
    user_data = {
        "username": payload.username,
        "email": payload.email.lower(),
        "password": payload.password,  # repository must hash before storing
        "full_name": payload.full_name.strip() if payload.full_name else None,
    }

    try:
        created = await create_user(user_data)
    except ValueError as exc:  # e.g. duplicate username/email raised by repo
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return UserResponse(
        id=created["id"],
        username=created["username"],
        email=created["email"],
        full_name=created.get("full_name"),
    )
