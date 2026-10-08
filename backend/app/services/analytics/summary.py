import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.query_log import QueryLog
from app.models.role import Role
from app.schemas.auth import CurrentUser
from app.schemas.dashboard import DashboardSummary, ModelCount, TenantQueryCount


def summarize(db: Session, current: CurrentUser) -> DashboardSummary:
    """Aggregate query_logs for the caller's tenant only."""
    rows = list(
        db.scalars(select(QueryLog).where(QueryLog.tenant_id == current.tenant_id)).all()
    )
    total = len(rows)
    hits = sum(1 for row in rows if row.cache_hit)
    latencies = [float(row.latency_ms) for row in rows]
    input_tokens = sum(row.input_tokens for row in rows)
    output_tokens = sum(row.output_tokens for row in rows)
    estimated_cost = sum(float(row.estimated_cost) for row in rows)
    cost_saved = sum(float(row.cost_saved) for row in rows)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.model] = counts.get(row.model, 0) + 1
    breakdown = None
    if current.role == Role.ADMIN:
        breakdown = [TenantQueryCount(tenant_id=current.tenant_id, total_queries=total)]
    return DashboardSummary(
        tenant_id=current.tenant_id,
        total_queries=total,
        cache_hits=hits,
        cache_misses=total - hits,
        hit_rate=round(hits / total, 4) if total else 0.0,
        average_latency_ms=round(sum(latencies) / total, 1) if total else 0.0,
        p95_latency_ms=round(_percentile(latencies, 0.95), 1),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=round(estimated_cost, 6),
        estimated_cost_saved=round(cost_saved, 6),
        model_distribution=[
            ModelCount(model=model, total_queries=count)
            for model, count in sorted(counts.items())
        ],
        queries_by_tenant=breakdown,
    )


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * fraction
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight

