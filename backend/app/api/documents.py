from fastapi import APIRouter

from app.api.errors import not_ready

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("")
def list_documents() -> None:
    raise not_ready("Document ingestion", "phase 3")


@router.post("")
def upload_document() -> None:
    raise not_ready("Document ingestion", "phase 3")
