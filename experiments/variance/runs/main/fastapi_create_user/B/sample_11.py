import hashlib
import os
from typing import Annotated, Callable
from uuid import uuid4

from fastapi import Body, Depends, FastAPI, HTTPException, status

app = FastAPI()

_USERS: dict[str, dict] = {}


def save_user(user: dict) -> dict:
    """Repository function: persists a user (in-memory here; swap for a real DB)."""
    if any(u["email"] == user["email"] or u["username"] == user["username"] for u in _USERS.values()):
        raise ValueError("User with this username or email already exists")
    user_id = str(uuid4())
    record = {"id": user_id, **user}
    _USERS[user_id] = record
    return record


def get_save_user() -> Callable[[dict], dict]:
    """Dependency provider; override via app.dependency_overrides in tests."""
    return save_user


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


@app.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    username: Annotated[str, Body(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_]+$")],
    email: Annotated[str, Body(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")],
    password: Annotated[str, Body(min_length=8, max_length=128)],
    save: Annotated[Callable[[dict], dict], Depends(get_save_user)],
    age: Annotated[int | None, Body(ge=0, le=150)] = None,
) -> dict:
    try:
        saved = save(
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
