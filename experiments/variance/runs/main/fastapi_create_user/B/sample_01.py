from typing import Annotated, Callable, Awaitable

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

app = FastAPI()


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    age: int | None = Field(default=None, ge=13, le=120)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    age: int | None = None


class DuplicateUserError(Exception):
    pass


SaveUser = Callable[[UserCreate], Awaitable[UserRead]]


async def save_user(user: UserCreate) -> UserRead:
    """Repository function: replace with real persistence (DB, ORM, etc.).

    Should raise DuplicateUserError if the username/email already exists
    and must store a hashed password, never the plaintext one.
    """
    raise NotImplementedError("Wire up a real repository implementation")


def get_save_user() -> SaveUser:
    """Dependency provider; override in tests via app.dependency_overrides."""
    return save_user


@app.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    save: Annotated[SaveUser, Depends(get_save_user)],
) -> UserRead:
    try:
        return await save(payload)
    except DuplicateUserError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this username or email already exists.",
        )
