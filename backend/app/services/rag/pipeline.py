import logging
import time
import uuid

from sqlalchemy.orm import Session

from app.config import Settings
from app.models.query_log import QueryLog
from app.schemas.auth import CurrentUser
from app.schemas.rag import RagQueryResponse, SourceResponse
from app.services.cache.semantic_cache import CacheHit, SemanticCache, permission_context
from app.services.exceptions import IngestionError
from app.services.ingestion.embedding_service import EmbeddingService
from app.services.rag.preprocess import preprocess_query
from app.vector_dimensions import EMBEDDING_VECTOR_DIMENSION
from app.services.rag.prompt import build_prompt
from app.services.rag.providers import LLMProvider
from app.services.retrieval import search as retrieval_search
from app.services.routing.router import decide, estimate_cost
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
    cache: SemanticCache | None = None,
    top_k: int | None = None,
    similarity_threshold: float | None = None,
    department: str | None = None,
    access_level: str | None = None,
) -> RagQueryResponse:
    """Retrieve allowed chunks, reuse a safe cached answer, or ask the routed model."""
    started = time.perf_counter()
    question = preprocess_query(query)
    department = department.strip() if department else None
    if department == "":
        department = None
    access_level = access_level.strip() if access_level else None
    if access_level == "":
        access_level = None
    embedding = _embed(embedder, question)
    context = permission_context(
        role=current.role,
        department=current.department,
        access_level=access_level,
        department_filter=department,
    )
    tenant_id = str(current.tenant_id)
    if cache is not None:
        hit = cache.lookup(tenant_id=tenant_id, permission=context, embedding=embedding)
        if hit is not None:
            return _finish_hit(
                db,
                current,
                cache,
                question=question,
                request_id=request_id,
                hit=hit,
                started=started,
            )
        cache.record_miss(tenant_id)

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
        query_embedding=embedding,
    )
    ranked = sorted(chunks, key=lambda chunk: chunk.score, reverse=True)
    decision = decide(question, chunks=ranked, settings=settings)
    system, user = build_prompt(question, ranked)
    result = provider.complete(system=system, user=user, chunks=ranked, model=decision.model)
    latency_ms = (time.perf_counter() - started) * 1000
    sources = [_source(chunk) for chunk in ranked]
    cost = estimate_cost(result.input_tokens, result.output_tokens, decision)
    source_payload = [source.model_dump(mode="json") for source in sources]
    if cache is not None and source_payload:
        cache.store(
            tenant_id=tenant_id,
            permission=context,
            query=question,
            embedding=embedding,
            answer=result.answer,
            sources=source_payload,
            model=result.model,
            latency_ms=latency_ms,
            estimated_cost=cost,
        )
    _write_log(
        db,
        current,
        request_id=request_id,
        question=question,
        answer=result.answer,
        sources=source_payload,
        model=result.model,
        cache_hit=False,
        latency_ms=latency_ms,
        chunk_count=len(ranked),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        estimated_cost=cost,
        cost_saved=0,
    )
    return RagQueryResponse(
        answer=result.answer,
        sources=sources,
        model_used=result.model,
        cache_hit=False,
        latency=round(latency_ms, 1),
        request_id=request_id,
    )


def _finish_hit(
    db: Session,
    current: CurrentUser,
    cache: SemanticCache,
    *,
    question: str,
    request_id: str,
    hit: CacheHit,
    started: float,
) -> RagQueryResponse:
    latency_ms = (time.perf_counter() - started) * 1000
    sources = [SourceResponse.model_validate(item) for item in hit.sources]
    cache.record_hit(str(current.tenant_id), cost_saved=hit.saved_cost, latency_saved_ms=hit.saved_latency_ms)
    _write_log(
        db,
        current,
        request_id=request_id,
        question=question,
        answer=hit.answer,
        sources=hit.sources,
        model=hit.model,
        cache_hit=True,
        latency_ms=latency_ms,
        chunk_count=len(sources),
        input_tokens=0,
        output_tokens=0,
        estimated_cost=0,
        cost_saved=hit.saved_cost,
    )
    return RagQueryResponse(
        answer=hit.answer,
        sources=sources,
        model_used=hit.model,
        cache_hit=True,
        latency=round(latency_ms, 1),
        request_id=request_id,
    )


def _write_log(
    db: Session,
    current: CurrentUser,
    *,
    request_id: str,
    question: str,
    answer: str,
    sources: list[dict[str, object]],
    model: str,
    cache_hit: bool,
    latency_ms: float,
    chunk_count: int,
    input_tokens: int,
    output_tokens: int,
    estimated_cost: float,
    cost_saved: float,
) -> None:
    db.add(
        QueryLog(
            request_id=request_id,
            tenant_id=current.tenant_id,
            user_id=current.user_id,
            query=question,
            answer=answer,
            sources=sources,
            model=model,
            cache_hit=cache_hit,
            latency_ms=latency_ms,
            retrieved_chunk_count=chunk_count,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=estimated_cost,
            cost_saved=cost_saved,
        )
    )
    db.commit()
    logger.info(
        "rag query",
        extra={
            "rag": {
                "request_id": request_id,
                "tenant_id": str(current.tenant_id),
                "user_id": str(current.user_id),
                "latency_ms": round(latency_ms, 1),
                "model": model,
                "cache_hit": cache_hit,
                "retrieved_chunk_count": chunk_count,
                "estimated_cost": estimated_cost,
            }
        },
    )


def _embed(embedder: EmbeddingService, text: str) -> list[float]:
    vectors = embedder.embed([text])
    if len(vectors) != 1 or len(vectors[0]) != EMBEDDING_VECTOR_DIMENSION:
        width = len(vectors[0]) if vectors else 0
        raise IngestionError(
            f"Query embedding length {width} does not match the stored width of {EMBEDDING_VECTOR_DIMENSION}."
        )
    return vectors[0]


def _source(chunk: RetrievedChunk) -> SourceResponse:
    return SourceResponse(
        document_id=uuid.UUID(chunk.document_id),
        chunk_id=uuid.UUID(chunk.chunk_id),
        filename=chunk.filename,
        page_number=chunk.page_number,
        score=chunk.score,
        excerpt=chunk.content,
    )


