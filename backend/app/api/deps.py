"""Request dependencies.

Authenticated callers resolve to user_id, tenant_id, and role from the database.
The tenant id in the token must match the user row. Callers cannot supply tenant scope.
"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import user_repository
from app.schemas.auth import CurrentUser
from app.security.jwt import decode_access_token
from app.services.exceptions import Unauthorized

_bearer = HTTPBearer(auto_error=False)


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CurrentUser | None:
    if credentials is None:
        return None
    return _user_from_token(credentials.credentials, db)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if credentials is None:
        raise Unauthorized("Not authenticated")
    return _user_from_token(credentials.credentials, db)


def _user_from_token(token: str, db: Session) -> CurrentUser:
    claims = decode_access_token(token)
    user = user_repository.get_by_id(db, claims.user_id)
    if user is None or user.tenant_id != claims.tenant_id:
        raise Unauthorized("Invalid token")
    return CurrentUser(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        email=user.email,
        department=user.department,
    )
