import re
from typing import Awaitable, Callable, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

app = FastAPI()

EMAIL_MAX_LENGTH = 254
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")


class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip()
        if not USERNAME_PATTERN.fullmatch(value):
            raise ValueError(
                "Username may contain only letters, digits, '_', '.', '-' "
                "and must be 3-30 characters long."
            )
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if len(value) > EMAIL_MAX_LENGTH:
            raise ValueError("Email is too long.")
        return value.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain a lowercase letter.")
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain an uppercase letter.")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain a digit.")
        return value


class SignupResponse(BaseModel):
    id: str
    username: str
    email: EmailStr


UserRecord = dict
CreateUserFn = Callable[[str, str, str], Awaitable[Optional[UserRecord]]]


async def create_user_placeholder(
    username: str, email: str, password_hash: str
) -> Optional[UserRecord]:
    """Default repository function; override via app.dependency_overrides
    or replace get_create_user with a real implementation.

    Must return the stored user record (with 'id', 'username', 'email'),
    or None if the username/email already exists.
    """
    raise NotImplementedError("Repository function is not configured.")


def get_create_user() -> CreateUserFn:
    return create_user_placeholder


def hash_password(password: str) -> str:
    import base64
    import hashlib
    import os

    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32
    )
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


@app.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    payload: SignupRequest,
    create_user: CreateUserFn = Depends(get_create_user),
) -> SignupResponse:
    password_hash = hash_password(payload.password)

    try:
        user = await create_user(payload.username, payload.email, password_hash)
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User storage is not available.",
        )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered.",
        )

    return SignupResponse(
        id=str(user["id"]),
        username=user["username"],
        email=user["email"],
    )
