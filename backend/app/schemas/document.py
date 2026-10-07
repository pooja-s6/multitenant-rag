from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ChunkResponse(BaseModel):
    id: UUID
    chunk_index: int
    page_number: int | None
    content: str


class DocumentPermissionResponse(BaseModel):
    access_level: str
    department: str | None
    allowed_roles: list[str]


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    filename: str
    content_type: str
    uploaded_by: UUID | None
    file_size: int
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class DocumentDetail(DocumentSummary):
    permission: DocumentPermissionResponse
    chunks: list[ChunkResponse]
