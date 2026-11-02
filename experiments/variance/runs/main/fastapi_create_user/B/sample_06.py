from typing import Annotated, Callable, Awaitable

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

app = FastAPI()


class UserCreate(BaseModel):
    username: Annotated[str, Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")]
    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=128)]
    age: Annotated[int | None, Field(ge=13, le=120)] = None

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.lower()


class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    age: int | None = None


class DuplicateUserError(Exception):
    pass


SaveUser = Callable[[UserCreate], Awaitable[UserRead]]


async def save_user(user: UserCreate) -> UserRead:
    """Default repository function. Replace with a real database implementation.

    Should raise DuplicateUserError if the username or email already exists.
    """
    raise NotImplementedError("Provide a real repository via dependency_overrides")


def get_save_user() -> SaveUser:
    return save_user


@app.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    save: Annotated[SaveUser, Depends(get_save_user)],
) -> UserRead:
    try:
        return await save(user)
    except DuplicateUserError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with that username or email already exists.",
        )
