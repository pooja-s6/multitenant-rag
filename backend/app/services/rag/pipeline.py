import logging
import time
import uuid

from sqlalchemy.orm import Session

from app.config import Settings
from app.models.query_log import QueryLog
from app.schemas.auth import CurrentUser
from app.schemas.rag import RagQueryResponse, SourceResponse
from app.services.ingestion.embedding_service import EmbeddingService
from app.services.rag.preprocess import preprocess_query
from app.services.rag.prompt import build_prompt
from app.services.rag.providers import LLMProvider
from app.services.retrieval import search as retrieval_search
from app.services.retrieval.search import RetrievedChunk

logger = logging.getLogger(__name__)


def answer_query(
    db: Session,
    current: CurrentUser,
    *,
    query: str,
    request_id: str,
    settings: Settings,
    embedder: EmbeddingService,
    provider: LLMProvider,
    top_k: int | None = None,
    similarity_threshold: float | None = None,
    department: str | None = None,
    access_level: str | None = None,
) -> RagQueryResponse:
    """Retrieve allowed chunks, ask the provider, and store a query log.

    Semantic cache is not consulted. cache_hit is always false until phase 6.
    Model routing is not applied. The configured small model is used until phase 7.
    """
    started = time.perf_counter()
    question = preprocess_query(query)
    chunks = retrieval_search.search(
        db,
        current,
        query=question,
        settings=settings,
        embedder=embedder,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
        department=department,
        access_level=access_level,
    )
    ranked = sorted(chunks, key=lambda chunk: chunk.score, reverse=True)
    system, user = build_prompt(question, ranked)
    result = provider.complete(system=system, user=user, chunks=ranked)
    latency_ms = (time.perf_counter() - started) * 1000
    sources = [_source(chunk) for chunk in ranked]
    cost = _estimate_cost(result.input_tokens, result.output_tokens, settings)
    db.add(
        QueryLog(
            request_id=request_id,
            tenant_id=current.tenant_id,
            user_id=current.user_id,
            query=question,
            answer=result.answer,
            sources=[source.model_dump(mode="json") for source in sources],
            model=result.model,
            cache_hit=False,
            latency_ms=latency_ms,
            retrieved_chunk_count=len(ranked),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            estimated_cost=cost,
        )
    )
    db.commit()
    logger.info(
        "rag query request_id=%s tenant_id=%s user_id=%s model=%s cache_hit=false chunks=%s latency_ms=%.1f estimated_cost=%.6f",
        request_id,
        current.tenant_id,
        current.user_id,
        result.model,
        len(ranked),
        latency_ms,
        cost,
    )
    return RagQueryResponse(
        answer=result.answer,
        sources=sources,
        model_used=result.model,
        cache_hit=False,
        latency=round(latency_ms, 1),
        request_id=request_id,
    )


def _source(chunk: RetrievedChunk) -> SourceResponse:
    return SourceResponse(
        document_id=uuid.UUID(chunk.document_id),
        chunk_id=uuid.UUID(chunk.chunk_id),
        filename=chunk.filename,
        page_number=chunk.page_number,
        score=chunk.score,
        excerpt=chunk.content,
    )


def _estimate_cost(input_tokens: int, output_tokens: int, settings: Settings) -> float:
    """USD using the small-model prices. Routing prices arrive in phase 7."""
    input_cost = input_tokens / 1_000_000 * settings.small_model_price
    output_cost = output_tokens / 1_000_000 * settings.small_model_output_price
    return input_cost + output_cost
