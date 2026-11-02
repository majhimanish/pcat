import re
from typing import Any, Awaitable, Callable, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field, field_validator

app = FastAPI()

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

CreateUserFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
GetUserByEmailFn = Callable[[str], Awaitable[Optional[dict[str, Any]]]]


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_PATTERN.match(value):
            raise ValueError("Invalid email address")
        return value


class UserRead(BaseModel):
    id: int
    username: str
    email: str


def get_create_user_fn() -> CreateUserFn:
    """Dependency provider; override in app.dependency_overrides or wire to a real repository."""
    raise NotImplementedError("create_user repository function not configured")


def get_user_by_email_fn() -> GetUserByEmailFn:
    """Dependency provider; override in app.dependency_overrides or wire to a real repository."""
    raise NotImplementedError("get_user_by_email repository function not configured")


def hash_password(password: str) -> str:
    import hashlib
    import os

    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return salt.hex() + ":" + digest.hex()


@app.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(
    payload: UserCreate,
    create_user: CreateUserFn = Depends(get_create_user_fn),
    get_user_by_email: GetUserByEmailFn = Depends(get_user_by_email_fn),
) -> UserRead:
    existing = await get_user_by_email(payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    try:
        created = await create_user(
            {
                "username": payload.username,
                "email": payload.email,
                "password_hash": hash_password(payload.password),
            }
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return UserRead(
        id=created["id"],
        username=created["username"],
        email=created["email"],
    )
