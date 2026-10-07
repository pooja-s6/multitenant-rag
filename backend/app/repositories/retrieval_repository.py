import uuid

from sqlalchemy import or_, select, true
from sqlalchemy.orm import Session

from app.models.access import AccessLevel
from app.models.document import DocumentChunk
from app.models.role import Role


def search(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    role: Role,
    caller_department: str | None,
    query_embedding: list[float],
    limit: int,
    minimum_similarity: float,
    department: str | None,
    access_level: AccessLevel | None,
) -> list[tuple[DocumentChunk, float]]:
    """Similarity search. Tenant and permission predicates run in the same query."""
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)
    similarity = (1 - distance).label("similarity")
    statement = select(DocumentChunk, similarity).where(DocumentChunk.tenant_id == tenant_id)
    statement = statement.where(_permission_clause(role, caller_department))
    if department is not None:
        statement = statement.where(DocumentChunk.department == department)
    if access_level is not None:
        statement = statement.where(DocumentChunk.access_level == access_level)
    statement = statement.where(distance <= (1 - minimum_similarity))
    statement = statement.order_by(distance.asc()).limit(limit)
    return [(chunk, float(score)) for chunk, score in db.execute(statement).all()]


def _permission_clause(role: Role, caller_department: str | None):
    if role is Role.ADMIN:
        return true()
    checks = [DocumentChunk.access_level == AccessLevel.PUBLIC]
    if role is Role.MANAGER:
        checks.append(DocumentChunk.access_level == AccessLevel.INTERNAL)
    checks.append(
        (DocumentChunk.access_level == AccessLevel.PRIVATE) & DocumentChunk.allowed_roles.contains([role.value])
    )
    role_clause = or_(*checks)
    if caller_department is None:
        department_clause = DocumentChunk.department.is_(None)
    else:
        department_clause = or_(
            DocumentChunk.department.is_(None),
            DocumentChunk.department == caller_department,
        )
    return role_clause & department_clause
