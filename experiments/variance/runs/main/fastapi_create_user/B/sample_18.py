from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)


class UserRead(BaseModel):
    id: int
    email: EmailStr
    username: str
    full_name: str | None = None


class DuplicateUserError(Exception):
    pass


def get_create_user():
    """Dependency provider for the create-user repository function.

    Override via app.dependency_overrides[get_create_user] or replace this
    body to return the real repository function.
    """
    raise NotImplementedError("create_user repository function is not configured")


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user_route(
    payload: UserCreate,
    create_user=Depends(get_create_user),
) -> UserRead:
    try:
        user = await create_user(
            email=payload.email,
            username=payload.username,
            password=payload.password,
            full_name=payload.full_name,
        )
    except DuplicateUserError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email or username already exists",
        )
    return user
