import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentChunk


def add(db: Session, document: Document) -> Document:
    db.add(document)
    return document


def add_chunk(db: Session, chunk: DocumentChunk) -> DocumentChunk:
    db.add(chunk)
    return chunk


def get_for_tenant(db: Session, document_id: uuid.UUID, tenant_id: uuid.UUID) -> Document | None:
    return db.scalar(
        select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
    )


def list_for_tenant(db: Session, tenant_id: uuid.UUID) -> list[tuple[Document, int]]:
    chunk_count = func.count(DocumentChunk.id)
    rows = db.execute(
        select(Document, chunk_count)
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .where(Document.tenant_id == tenant_id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    ).all()
    return [(document, int(count)) for document, count in rows]


def list_chunks(db: Session, document_id: uuid.UUID, tenant_id: uuid.UUID) -> list[DocumentChunk]:
    rows = db.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id, DocumentChunk.tenant_id == tenant_id)
        .order_by(DocumentChunk.chunk_index)
    )
    return list(rows)


def delete(db: Session, document: Document) -> None:
    db.delete(document)
