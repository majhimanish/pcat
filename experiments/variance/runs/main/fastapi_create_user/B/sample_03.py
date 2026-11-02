from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(..., min_length=8, max_length=128)


class UserRead(BaseModel):
    id: int
    email: EmailStr
    username: str


def get_create_user():
    """Dependency provider for the create-user repository function.

    Override via app.dependency_overrides or replace with a real implementation
    that returns an async callable: (email, username, password) -> dict | None.
    """
    raise NotImplementedError("create_user repository dependency is not configured")


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user_handler(
    payload: UserCreate,
    create_user=Depends(get_create_user),
) -> UserRead:
    try:
        user = await create_user(
            email=payload.email,
            username=payload.username,
            password=payload.password,
        )
    except ValueError as exc:
        # Repository signals duplicate email/username or other domain conflicts.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User could not be created",
        )
    return UserRead(**user)
