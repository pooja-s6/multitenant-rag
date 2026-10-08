from uuid import UUID

from pydantic import BaseModel


class ModelCount(BaseModel):
    model: str
    total_queries: int


class TenantQueryCount(BaseModel):
    tenant_id: UUID
    total_queries: int


class DashboardSummary(BaseModel):
    tenant_id: UUID
    total_queries: int
    cache_hits: int
    cache_misses: int
    hit_rate: float
    average_latency_ms: float
    p95_latency_ms: float
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    estimated_cost_saved: float
    model_distribution: list[ModelCount]
    queries_by_tenant: list[TenantQueryCount] | None = None
