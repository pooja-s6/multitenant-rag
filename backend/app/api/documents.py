from uuid import UUID

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.schemas.auth import CurrentUser
from app.schemas.document import DocumentDetail, DocumentSummary
from app.services.exceptions import BadRequest
from app.services.ingestion import document_service
from app.services.ingestion.embedding_service import EmbeddingService, get_embedding_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
    embedder: EmbeddingService = Depends(get_embedding_service),
) -> DocumentDetail:
    if not file.filename:
        raise BadRequest("A filename is required.")
    settings = get_settings()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)
    return document_service.ingest_document(
        db,
        current,
        filename=file.filename,
        content_type=file.content_type,
        data=data,
        settings=settings,
        embedder=embedder,
    )


@router.get("", response_model=list[DocumentSummary])
def list_documents(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> list[DocumentSummary]:
    return document_service.list_documents(db, current)


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> DocumentDetail:
    return document_service.get_document(db, current, document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> Response:
    document_service.delete_document(db, current, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
