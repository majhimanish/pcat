import hashlib
import os
import re
from typing import Annotated, Any, Callable, Optional

from fastapi import Body, Depends, FastAPI, HTTPException, status

app = FastAPI()

CreateUserFn = Callable[[dict[str, Any]], Optional[dict[str, Any]]]

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def get_create_user_fn() -> CreateUserFn:
    """Dependency provider. Override via app.dependency_overrides in tests
    or replace with a function returning a real DB-backed implementation.

    The returned function persists the user and returns the stored record,
    or returns None if a user with the same email already exists.
    """
    raise NotImplementedError("Provide a repository create_user function")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


def validate_user_input(email: str, username: str, password: str) -> dict[str, str]:
    errors: dict[str, str] = {}

    email = email.strip().lower()
    username = username.strip()

    if len(email) > 254 or not EMAIL_PATTERN.match(email):
        errors["email"] = "Invalid email address."
    if not re.fullmatch(r"[A-Za-z0-9_.\-]{3,32}", username):
        errors["username"] = (
            "Username must be 3-32 characters: letters, digits, '_', '.', '-'."
        )
    if len(password) < 8 or len(password) > 128:
        errors["password"] = "Password must be between 8 and 128 characters."
    elif not (
        re.search(r"[a-z]", password)
        and re.search(r"[A-Z]", password)
        and re.search(r"\d", password)
    ):
        errors["password"] = (
            "Password must include lowercase, uppercase, and a digit."
        )

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors
        )

    return {"email": email, "username": username}


@app.post("/users", status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    email: Annotated[str, Body(max_length=254)],
    username: Annotated[str, Body(max_length=64)],
    password: Annotated[str, Body(max_length=128)],
    create_user: Annotated[CreateUserFn, Depends(get_create_user_fn)],
) -> dict[str, Any]:
    cleaned = validate_user_input(email, username, password)

    record = {
        "email": cleaned["email"],
        "username": cleaned["username"],
        "password_hash": hash_password(password),
    }

    created = create_user(record)
    if created is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    return {k: v for k, v in created.items() if k != "password_hash"}
