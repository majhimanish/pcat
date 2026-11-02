import re
from typing import Awaitable, Callable, Optional

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

EMAIL_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip()
        if not EMAIL_USERNAME_PATTERN.match(value):
            raise ValueError(
                "Username may contain only letters, digits, '_', '.', and '-'."
            )
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not (
            re.search(r"[A-Z]", value)
            and re.search(r"[a-z]", value)
            and re.search(r"\d", value)
        ):
            raise ValueError(
                "Password must contain upper-case, lower-case, and a digit."
            )
        return value


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    full_name: Optional[str] = None


CreateUserFn = Callable[[dict], Awaitable[dict]]


def get_create_user_fn() -> CreateUserFn:
    """Dependency provider; override in app/tests with a real repository function."""
    raise NotImplementedError("create_user repository function not configured")


async def create_user_endpoint(
    payload: UserCreateRequest,
    create_user: CreateUserFn = Depends(get_create_user_fn),
) -> UserResponse:
    """POST /users handler. Register with:
    router.post("/users", response_model=UserResponse,
                status_code=status.HTTP_201_CREATED)(create_user_endpoint)
    """
    user_data = {
        "username": payload.username,
        "email": payload.email.lower(),
        "password": payload.password,  # repository is responsible for hashing
        "full_name": payload.full_name,
    }

    try:
        created = await create_user(user_data)
    except ValueError as exc:  # e.g. duplicate username/email raised by repository
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return UserResponse(
        id=created["id"],
        username=created["username"],
        email=created["email"],
        full_name=created.get("full_name"),
    )
