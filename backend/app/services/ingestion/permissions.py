from dataclasses import dataclass

from app.models.access import AccessLevel
from app.models.role import Role
from app.services.exceptions import BadRequest

_PUBLIC_ROLES = [Role.ADMIN.value, Role.MANAGER.value, Role.USER.value]
_INTERNAL_ROLES = [Role.ADMIN.value, Role.MANAGER.value]


@dataclass(frozen=True)
class ResolvedPermission:
    access_level: AccessLevel
    department: str | None
    allowed_roles: list[str]


def resolve_permission(
    *,
    access_level: str | None,
    department: str | None,
    allowed_roles: str | None,
    uploader_role: Role,
) -> ResolvedPermission:
    """Turn upload fields into the rules stored on the document and its chunks."""
    level = _parse_level(access_level)
    cleaned_department = _clean_department(department)
    if level is AccessLevel.PUBLIC:
        roles = list(_PUBLIC_ROLES)
    elif level is AccessLevel.INTERNAL:
        roles = list(_INTERNAL_ROLES)
    else:
        roles = _parse_roles(allowed_roles) or [uploader_role.value]
    return ResolvedPermission(access_level=level, department=cleaned_department, allowed_roles=roles)


def _parse_level(value: str | None) -> AccessLevel:
    raw = (value or AccessLevel.INTERNAL.value).strip().lower()
    try:
        return AccessLevel(raw)
    except ValueError as exc:
        raise BadRequest("access_level must be public, internal, or private.") from exc


def _clean_department(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > 120:
        raise BadRequest("department must be 120 characters or fewer.")
    return cleaned


def _parse_roles(value: str | None) -> list[str]:
    if value is None or not value.strip():
        return []
    roles: list[str] = []
    for part in value.split(","):
        name = part.strip().upper()
        if not name:
            continue
        try:
            role = Role(name)
        except ValueError as exc:
            raise BadRequest("allowed_roles must be a list of ADMIN, MANAGER, or USER.") from exc
        if role.value not in roles:
            roles.append(role.value)
    return roles
