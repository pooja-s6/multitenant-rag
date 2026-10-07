from uuid import UUID

from pydantic import BaseModel, Field


class RagQueryRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1)
    similarity_threshold: float | None = Field(default=None, le=1)
    department: str | None = None
    access_level: str | None = None


class SourceResponse(BaseModel):
    document_id: UUID
    chunk_id: UUID
    filename: str
    page_number: int | None
    score: float
    excerpt: str


class RagQueryResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]
    model_used: str
    cache_hit: bool
    latency: float
    request_id: str
