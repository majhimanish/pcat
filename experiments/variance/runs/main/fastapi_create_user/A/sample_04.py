import re
from typing import Awaitable, Callable, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

app = FastAPI()

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not USERNAME_PATTERN.match(value):
            raise ValueError(
                "username may only contain letters, digits, underscores, dots and hyphens"
            )
        return value.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not (
            any(c.islower() for c in value)
            and any(c.isupper() for c in value)
            and any(c.isdigit() for c in value)
        ):
            raise ValueError(
                "password must contain upper-case, lower-case and numeric characters"
            )
        return value


class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    full_name: Optional[str] = None


CreateUserFn = Callable[[dict], Awaitable[dict]]


def get_create_user_fn() -> CreateUserFn:
    """Dependency provider; override in app.dependency_overrides or replace with a real repository."""

    async def not_configured(user_data: dict) -> dict:
        raise NotImplementedError("Repository create_user function is not configured")

    return not_configured


@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(
    payload: UserCreate,
    create_user: CreateUserFn = Depends(get_create_user_fn),
) -> UserOut:
    user_data = {
        "username": payload.username,
        "email": payload.email.lower(),
        "password": payload.password,  # repository is responsible for hashing
        "full_name": payload.full_name,
    }

    try:
        created = await create_user(user_data)
    except ValueError as exc:
        # Repository signals duplicate / constraint violations with ValueError
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    return UserOut(**created)
