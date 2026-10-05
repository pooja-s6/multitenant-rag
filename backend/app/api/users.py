from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.schemas.auth import CurrentUser
from app.schemas.user import UserCreate, UserResponse
from app.services import users as user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> list[UserResponse]:
    return [UserResponse.model_validate(user) for user in user_service.list_users(db, current)]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(user_service.create_user(db, current, body))
