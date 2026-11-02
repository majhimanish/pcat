import re
from typing import Awaitable, Callable, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field, field_validator

app = FastAPI()

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

CreateUserFn = Callable[[dict], Awaitable[dict]]


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_PATTERN.match(value):
            raise ValueError("Invalid email address")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not (any(c.isalpha() for c in value) and any(c.isdigit() for c in value)):
            raise ValueError("Password must contain at least one letter and one digit")
        return value


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None


def get_create_user_fn() -> CreateUserFn:
    """Dependency provider; override in app.dependency_overrides or replace with a real repository function."""
    raise NotImplementedError("create_user repository function is not configured")


@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(
    payload: UserCreate,
    create_user: CreateUserFn = Depends(get_create_user_fn),
) -> UserOut:
    try:
        created = await create_user(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return UserOut(**created)
