from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.schemas.auth import CurrentUser
from app.schemas.retrieval import RetrievalRequest, RetrievalResponse, RetrievedChunkResponse
from app.services.ingestion.embedding_service import EmbeddingService, get_embedding_service
from app.services.retrieval import search as retrieval_search

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/search", response_model=RetrievalResponse)
def search_documents(
    body: RetrievalRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
    embedder: EmbeddingService = Depends(get_embedding_service),
) -> RetrievalResponse:
    rows = retrieval_search.search(
        db,
        current,
        query=body.query,
        settings=get_settings(),
        embedder=embedder,
        top_k=body.top_k,
        similarity_threshold=body.similarity_threshold,
        department=body.department,
        access_level=body.access_level,
    )
    return RetrievalResponse(
        chunks=[
            RetrievedChunkResponse(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                filename=row.filename,
                content=row.content,
                page_number=row.page_number,
                access_level=row.access_level,
                department=row.department,
                score=row.score,
            )
            for row in rows
        ]
    )
