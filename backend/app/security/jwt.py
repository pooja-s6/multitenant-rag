from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from jwt import InvalidTokenError

from app.config import get_settings
from app.models.role import Role
from app.services.exceptions import Unauthorized


class TokenClaims:
    def __init__(self, user_id: UUID, tenant_id: UUID, role: str) -> None:
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role


def create_access_token(*, user_id: UUID, tenant_id: UUID, role: Role, department: str | None) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, object] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role.value,
        "exp": expires,
    }
    if department:
        payload["department"] = department
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> TokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError as exc:
        raise Unauthorized("Invalid token") from exc

    subject = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    role = payload.get("role")
    if not isinstance(subject, str) or not isinstance(tenant_id, str) or not isinstance(role, str):
        raise Unauthorized("Invalid token")
    try:
        return TokenClaims(user_id=UUID(subject), tenant_id=UUID(tenant_id), role=role)
    except ValueError as exc:
        raise Unauthorized("Invalid token") from exc
