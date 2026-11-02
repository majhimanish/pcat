from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("password must contain at least one letter and one digit")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    full_name: str | None = None


class DuplicateUserError(Exception):
    pass


_FAKE_DB: dict[int, dict[str, Any]] = {}


def hash_password(password: str) -> str:
    import hashlib
    import os

    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return salt.hex() + ":" + digest.hex()


def create_user_in_repo(payload: UserCreate) -> dict[str, Any]:
    """Repository function: persists the user and returns the stored record."""
    for row in _FAKE_DB.values():
        if row["username"] == payload.username or row["email"].lower() == payload.email.lower():
            raise DuplicateUserError("username or email already exists")
    user_id = len(_FAKE_DB) + 1
    record = {
        "id": user_id,
        "username": payload.username,
        "email": payload.email,
        "full_name": payload.full_name,
        "password_hash": hash_password(payload.password),
    }
    _FAKE_DB[user_id] = record
    return record


def get_create_user_repo():
    """Dependency provider; override in tests or swap for a real DB-backed function."""
    return create_user_in_repo


router = APIRouter()


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    create_user_fn: Annotated[Any, Depends(get_create_user_repo)],
) -> UserRead:
    try:
        created = create_user_fn(payload)
    except DuplicateUserError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserRead.model_validate(created) if not isinstance(created, dict) else UserRead(**{k: created[k] for k in ("id", "username", "email", "full_name")})


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


app = create_app()
