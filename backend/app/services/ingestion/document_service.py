import logging
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import Settings
from app.models.document import Document, DocumentChunk
from app.repositories import document_repository
from app.schemas.auth import CurrentUser
from app.schemas.document import DocumentDetail, DocumentSummary
from app.services.exceptions import BadRequest, IngestionError, NotFound, PayloadTooLarge
from app.services.ingestion.chunker import chunk_pages
from app.services.ingestion.embedding_service import EmbeddingService
from app.services.ingestion.text_extractor import extract_pages
from app.vector_dimensions import EMBEDDING_VECTOR_DIMENSION

logger = logging.getLogger(__name__)


def ingest_document(
    db: Session,
    current: CurrentUser,
    *,
    filename: str,
    content_type: str | None,
    data: bytes,
    settings: Settings,
    embedder: EmbeddingService,
) -> DocumentDetail:
    safe_name = Path(filename or "").name
    if not safe_name or safe_name in {".", ".."}:
        raise BadRequest("A filename is required.")
    if not data:
        raise BadRequest("File is empty.")
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise PayloadTooLarge(f"File exceeds the {settings.max_upload_size_mb} MB upload limit.")

    pages = extract_pages(safe_name, content_type, data)
    chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise BadRequest("Document has no extractable text. OCR is not supported.")

    vectors = embedder.embed([chunk.content for chunk in chunks])
    if len(vectors) != len(chunks):
        raise IngestionError("Embedding service returned an unexpected number of vectors.")
    for vector in vectors:
        if len(vector) != EMBEDDING_VECTOR_DIMENSION:
            raise IngestionError(
                f"Embedding length {len(vector)} does not match the stored width "
                f"of {EMBEDDING_VECTOR_DIMENSION}."
            )

    stored_type = (content_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    document = Document(
        tenant_id=current.tenant_id,
        filename=safe_name,
        content_type=stored_type or "application/octet-stream",
        uploaded_by=current.user_id,
        file_size=len(data),
    )
    try:
        document_repository.add(db, document)
        db.flush()
        for chunk, vector in zip(chunks, vectors, strict=True):
            document_repository.add_chunk(
                db,
                DocumentChunk(
                    document_id=document.id,
                    tenant_id=current.tenant_id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    page_number=chunk.page_number,
                    embedding=vector,
                    chunk_metadata={"filename": safe_name, "content_type": document.content_type},
                ),
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(document)
    logger.info(
        "ingested document id=%s tenant_id=%s chunks=%s filename=%s",
        document.id,
        current.tenant_id,
        len(chunks),
        safe_name,
    )
    return _detail(db, document)


def list_documents(db: Session, current: CurrentUser) -> list[DocumentSummary]:
    rows = document_repository.list_for_tenant(db, current.tenant_id)
    return [_summary(document, count) for document, count in rows]


def get_document(db: Session, current: CurrentUser, document_id: uuid.UUID) -> DocumentDetail:
    document = document_repository.get_for_tenant(db, document_id, current.tenant_id)
    if document is None:
        raise NotFound("Document not found")
    return _detail(db, document)


def delete_document(db: Session, current: CurrentUser, document_id: uuid.UUID) -> None:
    document = document_repository.get_for_tenant(db, document_id, current.tenant_id)
    if document is None:
        raise NotFound("Document not found")
    document_repository.delete(db, document)
    db.commit()
    logger.info("deleted document id=%s tenant_id=%s", document_id, current.tenant_id)


def _summary(document: Document, chunk_count: int) -> DocumentSummary:
    return DocumentSummary(
        id=document.id,
        tenant_id=document.tenant_id,
        filename=document.filename,
        content_type=document.content_type,
        uploaded_by=document.uploaded_by,
        file_size=document.file_size,
        chunk_count=chunk_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _detail(db: Session, document: Document) -> DocumentDetail:
    chunks = document_repository.list_chunks(db, document.id, document.tenant_id)
    summary = _summary(document, len(chunks))
    return DocumentDetail(
        **summary.model_dump(),
        chunks=[
            {
                "id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "content": chunk.content,
            }
            for chunk in chunks
        ],
    )
