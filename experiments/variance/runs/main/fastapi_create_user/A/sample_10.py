from typing import Callable, Awaitable, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

app = FastAPI()


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if not any(c.isdigit() for c in value) or not any(c.isalpha() for c in value):
            raise ValueError("Password must contain at least one letter and one digit")
        return value


class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    full_name: Optional[str] = None


CreateUserFn = Callable[[dict], Awaitable[dict]]


async def default_create_user_repo(user_data: dict) -> dict:
    raise NotImplementedError("Provide a real repository via dependency_overrides")


def get_create_user_repo() -> CreateUserFn:
    return default_create_user_repo


@app.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(
    payload: UserCreate,
    create_user: CreateUserFn = Depends(get_create_user_repo),
) -> UserRead:
    user_data = {
        "username": payload.username.strip().lower(),
        "email": payload.email.lower(),
        "password": payload.password,  # repository is responsible for hashing
        "full_name": payload.full_name.strip() if payload.full_name else None,
    }

    try:
        created = await create_user(user_data)
    except ValueError as exc:  # e.g. duplicate username/email raised by repository
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    return UserRead(**created)
