import re
from typing import Any, Awaitable, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

router = APIRouter()

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

CreateUserFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not EMAIL_PATTERN.match(value):
            raise ValueError("Invalid email address")
        return value.lower()


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None


def get_create_user_fn() -> CreateUserFn:
    """Dependency provider; override via app.dependency_overrides in
    production wiring and tests to inject the real repository function."""
    raise NotImplementedError("create_user repository function not configured")


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(
    payload: UserCreate,
    create_user: CreateUserFn = Depends(get_create_user_fn),
) -> UserOut:
    if payload.password.lower() in {payload.username.lower(), payload.email}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must not match username or email",
        )

    try:
        created = await create_user(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    return UserOut(**created)
