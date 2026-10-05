from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_user
from app.database import get_db
from app.schemas.auth import CurrentUser
from app.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate
from app.services import tenants as tenant_service

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    body: TenantCreate,
    db: Session = Depends(get_db),
    current: CurrentUser | None = Depends(get_optional_user),
) -> TenantResponse:
    tenant = tenant_service.create_tenant(db, body, current)
    return TenantResponse.model_validate(tenant)


@router.get("", response_model=list[TenantResponse])
def list_tenants(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> list[TenantResponse]:
    return [TenantResponse.model_validate(tenant) for tenant in tenant_service.list_tenants(db, current)]


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> TenantResponse:
    return TenantResponse.model_validate(tenant_service.get_tenant(db, current, tenant_id))


@router.patch("/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    tenant_id: UUID,
    body: TenantUpdate,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> TenantResponse:
    return TenantResponse.model_validate(tenant_service.update_tenant(db, current, tenant_id, body))


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> Response:
    tenant_service.delete_tenant(db, current, tenant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
