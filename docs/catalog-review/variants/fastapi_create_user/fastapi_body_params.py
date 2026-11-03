"""FastAPI create-user endpoint without Pydantic model classes.

Requires: fastapi>=0.110,<1. Each JSON field is a validated Body() parameter;
the repository function and the password hasher are injected with Depends.
Wire it with register_routes(app_or_router) and app.dependency_overrides.
"""

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Body, Depends, HTTPException, status

USERNAME_PATTERN = r"^[A-Za-z0-9_]{3,32}$"
EMAIL_PATTERN = r"^[^@\s]{1,64}@[^@\s.]{1,63}(\.[^@\s.]{1,63})+$"


def get_create_user() -> Callable[[dict[str, Any]], dict[str, Any] | None]:
    """Repository dependency: returns the stored user, or None if it already exists."""
    raise NotImplementedError("override get_create_user via app.dependency_overrides")


def get_password_hasher() -> Callable[[str], str]:
    raise NotImplementedError("override get_password_hasher via app.dependency_overrides")


def create_user(
    username: Annotated[str, Body(pattern=USERNAME_PATTERN)],
    email: Annotated[str, Body(max_length=254, pattern=EMAIL_PATTERN)],
    password: Annotated[str, Body(min_length=12, max_length=128)],
    save: Annotated[Callable[[dict[str, Any]], dict[str, Any] | None], Depends(get_create_user)],
    hash_password: Annotated[Callable[[str], str], Depends(get_password_hasher)],
) -> dict[str, Any]:
    """POST /users: validate, hash the password, store; 201 with the public fields."""
    user = save({
        "username": username,
        "email": email.lower(),
        "password_hash": hash_password(password),
    })
    if user is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "username or email already registered")
    return {"id": user["id"], "username": user["username"], "email": user["email"]}


def register_routes(app_or_router: Any) -> None:
    app_or_router.add_api_route(
        "/users", create_user, methods=["POST"], status_code=status.HTTP_201_CREATED
    )
