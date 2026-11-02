from typing import Annotated, Callable

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

app = FastAPI()


class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=100)
    age: int | None = Field(default=None, ge=0, le=150)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    full_name: str | None = None
    age: int | None = None


_USERS: dict[int, dict] = {}


def create_user_in_db(payload: UserCreate) -> dict:
    """Repository function: persists the user and returns the stored record."""
    for existing in _USERS.values():
        if existing["username"] == payload.username or existing["email"] == payload.email:
            raise ValueError("User with this username or email already exists")
    user_id = len(_USERS) + 1
    record = {"id": user_id, **payload.model_dump()}
    _USERS[user_id] = record
    return record


def get_create_user_repo() -> Callable[[UserCreate], dict]:
    """Dependency provider; override in tests or swap for a real DB-backed function."""
    return create_user_in_db


@app.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    create_user_repo: Annotated[Callable[[UserCreate], dict], Depends(get_create_user_repo)],
) -> dict:
    try:
        return create_user_repo(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
