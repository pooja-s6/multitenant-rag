from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.role import Role
from app.models.user import User
from app.repositories import tenant_repository, user_repository
from app.schemas.auth import CurrentUser
from app.schemas.user import UserCreate
from app.security.passwords import hash_password
from app.services.exceptions import Conflict, Forbidden, NotFound


def create_user(db: Session, current: CurrentUser, body: UserCreate) -> User:
    if current.role != Role.ADMIN:
        raise Forbidden("Insufficient permissions")

    email = body.email.lower()
    if user_repository.get_by_email(db, email) is not None:
        raise Conflict("Email already exists")

    tenant = tenant_repository.get_by_id(db, current.tenant_id)
    if tenant is None:
        raise NotFound("Tenant not found")
    user = User(
        tenant=tenant,
        email=email,
        password_hash=hash_password(body.password),
        role=body.role,
        department=body.department,
    )
    user_repository.add(db, user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("Email already exists") from exc
    db.refresh(user)
    return user


def list_users(db: Session, current: CurrentUser) -> list[User]:
    if current.role not in (Role.ADMIN, Role.MANAGER):
        raise Forbidden("Insufficient permissions")
    return user_repository.list_for_tenant(db, current.tenant_id)
