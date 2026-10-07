from pydantic import BaseModel, Field


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1)
    similarity_threshold: float | None = Field(default=None, le=1)
    department: str | None = None
    access_level: str | None = None


class RetrievedChunkResponse(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    content: str
    page_number: int | None
    access_level: str
    department: str | None
    score: float


class RetrievalResponse(BaseModel):
    chunks: list[RetrievedChunkResponse]
