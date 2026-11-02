import re
from typing import Any, Awaitable, Callable, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

app = FastAPI()

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: EmailStr
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

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not (
            re.search(r"[a-z]", value)
            and re.search(r"[A-Z]", value)
            and re.search(r"\d", value)
        ):
            raise ValueError(
                "password must contain lowercase, uppercase and digit characters"
            )
        return value


class UserPublic(BaseModel):
    id: int
    username: str
    email: EmailStr
    full_name: Optional[str] = None


CreateUserFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def get_create_user_fn() -> CreateUserFn:
    """Dependency provider; override via app.dependency_overrides in
    production wiring or tests to inject the real repository function."""
    raise NotImplementedError("create_user repository function not configured")


@app.post(
    "/users",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_endpoint(
    payload: UserCreate,
    create_user: CreateUserFn = Depends(get_create_user_fn),
) -> UserPublic:
    user_data = {
        "username": payload.username,
        "email": payload.email.lower(),
        "password": payload.password,  # repository is responsible for hashing
        "full_name": payload.full_name,
    }

    try:
        created = await create_user(user_data)
    except ValueError as exc:
        # Repository signals a duplicate / constraint violation via ValueError
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return UserPublic(**created)
