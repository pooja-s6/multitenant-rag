import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User


def count(db: Session) -> int:
    total = db.scalar(select(func.count()).select_from(User))
    return int(total or 0)


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def list_for_tenant(db: Session, tenant_id: uuid.UUID) -> list[User]:
    rows = db.scalars(
        select(User).where(User.tenant_id == tenant_id).order_by(User.created_at, User.email)
    )
    return list(rows)


def add(db: Session, user: User) -> User:
    db.add(user)
    return user
