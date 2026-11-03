import hashlib
import hmac
import os
import re
from itertools import count
from typing import Annotated, Callable

from fastapi import Body, Depends, FastAPI, HTTPException, status

app = FastAPI()

EMAIL_PATTERN = r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
USERNAME_PATTERN = r"^[A-Za-z0-9_]+$"

_USERS: dict[int, dict] = {}
_ID_SEQUENCE = count(1)

SaveUser = Callable[[dict], dict]


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


def save_user(user: dict) -> dict:
    """Repo function: persists a user (in-memory here; swap for a real DB)."""
    if any(u["email"] == user["email"] for u in _USERS.values()):
        raise ValueError("email already registered")
    if any(u["username"] == user["username"] for u in _USERS.values()):
        raise ValueError("username already taken")
    user_id = next(_ID_SEQUENCE)
    record = {"id": user_id, **user}
    _USERS[user_id] = record
    return record


def get_save_user() -> SaveUser:
    """Dependency provider; override in tests via app.dependency_overrides."""
    return save_user


def validate_password_strength(password: str) -> None:
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="password must contain at least one letter and one digit",
        )


@app.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    username: Annotated[str, Body(min_length=3, max_length=32, pattern=USERNAME_PATTERN)],
    email: Annotated[str, Body(max_length=254, pattern=EMAIL_PATTERN)],
    password: Annotated[str, Body(min_length=8, max_length=128)],
    age: Annotated[int | None, Body(ge=13, le=120)] = None,
    repo_save_user: SaveUser = Depends(get_save_user),
) -> dict:
    validate_password_strength(password)

    try:
        saved = repo_save_user(
            {
                "username": username,
                "email": email.lower(),
                "password_hash": hash_password(password),
                "age": age,
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    return {
        "id": saved["id"],
        "username": saved["username"],
        "email": saved["email"],
        "age": saved["age"],
    }
