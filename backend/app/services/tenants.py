import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories import tenant_repository, user_repository
from app.schemas.auth import CurrentUser
from app.schemas.tenant import TenantCreate, TenantUpdate
from app.security.passwords import hash_password
from app.services.exceptions import Conflict, Forbidden, NotFound, Unauthorized


def create_tenant(db: Session, body: TenantCreate, current: CurrentUser | None) -> Tenant:
    if user_repository.count(db) > 0:
        if current is None:
            raise Unauthorized("Not authenticated")
        if current.role != Role.ADMIN:
            raise Forbidden("Insufficient permissions")

    email = body.admin_email.lower()
    if tenant_repository.get_by_slug(db, body.slug) is not None:
        raise Conflict("Tenant slug already exists")
    if user_repository.get_by_email(db, email) is not None:
        raise Conflict("Email already exists")

    tenant = Tenant(name=body.name, slug=body.slug)
    user = User(
        tenant=tenant,
        email=email,
        password_hash=hash_password(body.admin_password),
        role=Role.ADMIN,
        department=body.admin_department,
    )
    tenant_repository.add(db, tenant)
    user_repository.add(db, user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("Tenant slug or admin email already exists") from exc
    db.refresh(tenant)
    return tenant


def list_tenants(db: Session, current: CurrentUser) -> list[Tenant]:
    tenant = _own_tenant(db, current)
    return [tenant]


def get_tenant(db: Session, current: CurrentUser, tenant_id: uuid.UUID) -> Tenant:
    if tenant_id != current.tenant_id:
        raise NotFound("Tenant not found")
    return _own_tenant(db, current)


def update_tenant(db: Session, current: CurrentUser, tenant_id: uuid.UUID, body: TenantUpdate) -> Tenant:
    _require_admin(current)
    tenant = get_tenant(db, current, tenant_id)
    tenant.name = body.name
    db.commit()
    db.refresh(tenant)
    return tenant


def delete_tenant(db: Session, current: CurrentUser, tenant_id: uuid.UUID) -> None:
    _require_admin(current)
    tenant = get_tenant(db, current, tenant_id)
    db.delete(tenant)
    db.commit()


def _own_tenant(db: Session, current: CurrentUser) -> Tenant:
    tenant = tenant_repository.get_by_id(db, current.tenant_id)
    if tenant is None:
        raise NotFound("Tenant not found")
    return tenant


def _require_admin(current: CurrentUser) -> None:
    if current.role != Role.ADMIN:
        raise Forbidden("Insufficient permissions")
