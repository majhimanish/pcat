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
        value = value.strip()
        if not USERNAME_PATTERN.fullmatch(value):
            raise ValueError("username may contain only letters, digits, '_', '.', and '-'")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not (re.search(r"[a-z]", value) and re.search(r"[A-Z]", value) and re.search(r"\d", value)):
            raise ValueError("password must contain upper-case, lower-case letters and a digit")
        return value


class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    full_name: Optional[str] = None


CreateUserFn = Callable[[dict], Awaitable[dict]]


async def get_create_user_fn() -> CreateUserFn:
    """Dependency provider; override in app.dependency_overrides or replace with real wiring."""
    raise NotImplementedError("create_user repository function is not configured")


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
    except ValueError as exc:  # e.g. duplicate username/email raised by the repository
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return UserOut(**created)
