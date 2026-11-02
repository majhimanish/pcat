from typing import Any, Callable, Dict

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

app = FastAPI()


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr


def get_create_user_repo() -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """Dependency provider. Override via app.dependency_overrides in tests
    or replace with a real repository-backed function."""
    def create_user(data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Repository function not configured")
    return create_user


def hash_password(password: str) -> str:
    import hashlib
    import os

    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return salt.hex() + ":" + digest.hex()


@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    payload: UserCreate,
    create_user: Callable[[Dict[str, Any]], Dict[str, Any]] = Depends(get_create_user_repo),
) -> UserOut:
    username = payload.username.strip()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username must not be blank",
        )

    user_data = {
        "username": username,
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
    }

    try:
        created = create_user(user_data)
    except ValueError as exc:
        # Repository signals duplicate/invalid data via ValueError
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    return UserOut(id=created["id"], username=created["username"], email=created["email"])
