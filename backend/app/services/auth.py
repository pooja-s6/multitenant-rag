from sqlalchemy.orm import Session

from app.config import get_settings
from app.repositories import user_repository
from app.schemas.auth import LoginRequest, TokenResponse
from app.security.jwt import create_access_token
from app.security.passwords import verify_password, verify_password_for_missing_user
from app.services.exceptions import Unauthorized


def login(db: Session, body: LoginRequest) -> TokenResponse:
    email = body.email.lower()
    user = user_repository.get_by_email(db, email)
    if user is None:
        verify_password_for_missing_user(body.password)
        raise Unauthorized("Invalid credentials")
    if not verify_password(body.password, user.password_hash):
        raise Unauthorized("Invalid credentials")

    settings = get_settings()
    token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        department=user.department,
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
    )
