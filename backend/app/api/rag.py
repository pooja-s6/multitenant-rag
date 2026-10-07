from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.schemas.auth import CurrentUser
from app.schemas.rag import RagQueryRequest, RagQueryResponse
from app.services.ingestion.embedding_service import EmbeddingService, get_embedding_service
from app.services.rag import pipeline
from app.services.rag.providers import LLMProvider, get_llm_provider

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query", response_model=RagQueryResponse)
def query(
    body: RagQueryRequest,
    request: Request,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
    embedder: EmbeddingService = Depends(get_embedding_service),
    provider: LLMProvider = Depends(get_llm_provider),
) -> RagQueryResponse:
    request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
    if not request_id:
        request_id = "missing-request-id"
    return pipeline.answer_query(
        db,
        current,
        query=body.query,
        request_id=str(request_id),
        settings=get_settings(),
        embedder=embedder,
        provider=provider,
        top_k=body.top_k,
        similarity_threshold=body.similarity_threshold,
        department=body.department,
        access_level=body.access_level,
    )
