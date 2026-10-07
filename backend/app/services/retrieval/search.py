from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import Settings
from app.models.access import AccessLevel
from app.repositories import retrieval_repository
from app.schemas.auth import CurrentUser
from app.services.exceptions import BadRequest, IngestionError
from app.services.ingestion.embedding_service import EmbeddingService
from app.vector_dimensions import EMBEDDING_VECTOR_DIMENSION


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    tenant_id: str
    filename: str
    content: str
    page_number: int | None
    access_level: str
    department: str | None
    score: float


def search(
    db: Session,
    current: CurrentUser,
    *,
    query: str,
    settings: Settings,
    embedder: EmbeddingService,
    top_k: int | None = None,
    similarity_threshold: float | None = None,
    department: str | None = None,
    access_level: str | None = None,
) -> list[RetrievedChunk]:
    """Return chunks the caller may read, nearest first.

    Extra filters can only remove rows. They cannot widen tenant, role, or department access.
    """
    text = query.strip()
    if not text:
        raise BadRequest("Query text is required.")
    limit = _narrow_top_k(top_k, settings.retrieval_top_k)
    threshold = _narrow_threshold(similarity_threshold, settings.retrieval_similarity_threshold)
    level = _parse_level(access_level)
    narrowed_department = _clean_department(department)

    vectors = embedder.embed([text])
    if len(vectors) != 1 or len(vectors[0]) != EMBEDDING_VECTOR_DIMENSION:
        width = len(vectors[0]) if vectors else 0
        raise IngestionError(
            f"Query embedding length {width} does not match the stored width "
            f"of {EMBEDDING_VECTOR_DIMENSION}."
        )

    rows = retrieval_repository.search(
        db,
        tenant_id=current.tenant_id,
        role=current.role,
        caller_department=current.department,
        query_embedding=vectors[0],
        limit=limit,
        minimum_similarity=threshold,
        department=narrowed_department,
        access_level=level,
    )
    return [
        RetrievedChunk(
            chunk_id=str(chunk.id),
            document_id=str(chunk.document_id),
            tenant_id=str(chunk.tenant_id),
            filename=chunk.chunk_metadata.get("filename", ""),
            content=chunk.content,
            page_number=chunk.page_number,
            access_level=chunk.access_level.value,
            department=chunk.department,
            score=float(score),
        )
        for chunk, score in rows
    ]


def _narrow_top_k(requested: int | None, configured: int) -> int:
    if requested is None:
        return configured
    if requested < 1 or requested > configured:
        raise BadRequest(f"top_k must be between 1 and {configured}.")
    return requested


def _narrow_threshold(requested: float | None, configured: float) -> float:
    if requested is None:
        return configured
    if requested < configured or requested > 1:
        raise BadRequest(
            f"similarity_threshold must be between {configured} and 1. A lower value would widen retrieval."
        )
    return requested


def _parse_level(value: str | None) -> AccessLevel | None:
    if value is None or not value.strip():
        return None
    try:
        return AccessLevel(value.strip().lower())
    except ValueError as exc:
        raise BadRequest("access_level must be public, internal, or private.") from exc


def _clean_department(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
