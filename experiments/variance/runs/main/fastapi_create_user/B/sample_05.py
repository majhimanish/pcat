from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, ConfigDict

app = FastAPI()

# In-memory store used by the default repository implementation.
_USERS: dict[int, dict] = {}


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=100)
    age: int | None = Field(default=None, ge=0, le=150)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    full_name: str | None = None
    age: int | None = None


def create_user_in_db(user: UserCreate) -> dict:
    """Repository function: persist a user and return the stored record."""
    for existing in _USERS.values():
        if existing["username"] == user.username or existing["email"] == user.email:
            raise ValueError("duplicate")
    new_id = len(_USERS) + 1
    record = {"id": new_id, **user.model_dump()}
    _USERS[new_id] = record
    return record


def get_create_user():
    """Dependency provider returning the repository function (override in tests)."""
    return create_user_in_db


@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    payload: UserCreate,
    create_user: Annotated[object, Depends(get_create_user)],
) -> UserOut:
    try:
        created = create_user(payload)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this username or email already exists",
        )
    return UserOut.model_validate(created)
