from typing import Annotated, Any, Awaitable, Callable

from fastapi import Depends, HTTPException, status
from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field

router = APIRouter(prefix="/users", tags=["users"])


class UserCreateRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username: str
    full_name: str | None = None


CreateUserFn = Callable[..., Awaitable[dict[str, Any]]]


def get_create_user_repository() -> CreateUserFn:
    """Dependency provider for the create-user repository function.

    Override via app.dependency_overrides or replace with a real implementation.
    """
    raise NotImplementedError("create_user repository is not configured")


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_handler(
    payload: UserCreateRequest,
    create_user: Annotated[CreateUserFn, Depends(get_create_user_repository)],
) -> UserResponse:
    try:
        created = await create_user(
            email=payload.email,
            username=payload.username,
            password=payload.password,
            full_name=payload.full_name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return UserResponse(**created)
