from typing import Annotated, Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

router = APIRouter(prefix="/users", tags=["users"])


class UserCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username: str
    full_name: str | None = None


class DuplicateUserError(Exception):
    pass


CreateUserFn = Callable[[UserCreateRequest], Awaitable[UserResponse]]


async def get_create_user() -> CreateUserFn:
    raise NotImplementedError("Provide a create-user repository function via dependency override")


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user_route(
    payload: UserCreateRequest,
    create_user: Annotated[CreateUserFn, Depends(get_create_user)],
) -> UserResponse:
    try:
        return await create_user(payload)
    except DuplicateUserError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email or username already exists",
        )
