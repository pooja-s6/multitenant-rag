import hashlib
import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.models.role import Role
from app.services.cache.store import CacheStore

MAX_ENTRIES_PER_CONTEXT = 50
_ENTRY_PREFIX = "rag:cache"
_STATS_PREFIX = "rag:cache-stats"


@dataclass(frozen=True)
class PermissionContext:
    role: str
    department: str | None
    access_level: str | None
    department_filter: str | None

    def digest(self) -> str:
        payload = json.dumps(
            {
                "role": self.role,
                "department": self.department,
                "access_level": self.access_level,
                "department_filter": self.department_filter,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class CacheHit:
    answer: str
    sources: list[dict[str, object]]
    model: str
    similarity: float
    saved_cost: float
    saved_latency_ms: float


@dataclass(frozen=True)
class CacheStats:
    hits: float
    misses: float
    cost_saved: float
    latency_saved_ms: float


class SemanticCache:
    def __init__(self, store: CacheStore, settings: Settings, *, max_entries: int = MAX_ENTRIES_PER_CONTEXT) -> None:
        self._store = store
        self._settings = settings
        self._max_entries = max_entries

    def lookup(
        self,
        *,
        tenant_id: str,
        permission: PermissionContext,
        embedding: list[float],
    ) -> CacheHit | None:
        best: CacheHit | None = None
        best_score = self._settings.cache_similarity_threshold
        for key in self._store.keys(self._entry_prefix(tenant_id, permission)):
            raw = self._store.get(key)
            if raw is None:
                continue
            entry = json.loads(raw)
            if not _entry_is_usable(entry, tenant_id, permission):
                continue
            score = cosine(embedding, entry["embedding"])
            if score >= best_score and (best is None or score > best.similarity):
                best_score = score
                best = CacheHit(
                    answer=entry["answer"],
                    sources=entry["sources"],
                    model=entry["model"],
                    similarity=score,
                    saved_cost=float(entry["estimated_cost"]),
                    saved_latency_ms=float(entry["latency_ms"]),
                )
        return best

    def store(
        self,
        *,
        tenant_id: str,
        permission: PermissionContext,
        query: str,
        embedding: list[float],
        answer: str,
        sources: list[dict[str, object]],
        model: str,
        latency_ms: float,
        estimated_cost: float,
    ) -> None:
        now = datetime.now(timezone.utc)
        entry = {
            "tenant_id": tenant_id,
            "permission": {
                "role": permission.role,
                "department": permission.department,
                "access_level": permission.access_level,
                "department_filter": permission.department_filter,
            },
            "query": query,
            "embedding": embedding,
            "answer": answer,
            "sources": sources,
            "model": model,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=self._settings.cache_ttl)).isoformat(),
            "latency_ms": latency_ms,
            "estimated_cost": estimated_cost,
        }
        prefix = self._entry_prefix(tenant_id, permission)
        self._trim(prefix)
        key = f"{prefix}{uuid.uuid4()}"
        self._store.set(key, json.dumps(entry), self._settings.cache_ttl)

    def record_hit(self, tenant_id: str, *, cost_saved: float, latency_saved_ms: float) -> None:
        self._store.add_float(self._stat_key(tenant_id, "hits"), 1)
        self._store.add_float(self._stat_key(tenant_id, "cost_saved"), cost_saved)
        self._store.add_float(self._stat_key(tenant_id, "latency_saved_ms"), latency_saved_ms)

    def record_miss(self, tenant_id: str) -> None:
        self._store.add_float(self._stat_key(tenant_id, "misses"), 1)

    def stats(self, tenant_id: str) -> CacheStats:
        return CacheStats(
            hits=self._store.read_float(self._stat_key(tenant_id, "hits")),
            misses=self._store.read_float(self._stat_key(tenant_id, "misses")),
            cost_saved=self._store.read_float(self._stat_key(tenant_id, "cost_saved")),
            latency_saved_ms=self._store.read_float(self._stat_key(tenant_id, "latency_saved_ms")),
        )

    def _trim(self, prefix: str) -> None:
        keys = self._store.keys(prefix)
        if len(keys) < self._max_entries:
            return
        dated: list[tuple[str, str]] = []
        for key in keys:
            raw = self._store.get(key)
            created = json.loads(raw)["created_at"] if raw else ""
            dated.append((created, key))
        dated.sort()
        for _, key in dated[: len(dated) - self._max_entries + 1]:
            self._store.delete(key)

    def _entry_prefix(self, tenant_id: str, permission: PermissionContext) -> str:
        return f"{_ENTRY_PREFIX}:{tenant_id}:{permission.digest()}:"

    def _stat_key(self, tenant_id: str, name: str) -> str:
        return f"{_STATS_PREFIX}:{tenant_id}:{name}"


def permission_context(
    *,
    role: Role | str,
    department: str | None,
    access_level: str | None,
    department_filter: str | None,
) -> PermissionContext:
    role_value = role.value if isinstance(role, Role) else role
    return PermissionContext(
        role=role_value,
        department=department,
        access_level=access_level,
        department_filter=department_filter,
    )


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _entry_is_usable(entry: dict[str, object], tenant_id: str, permission: PermissionContext) -> bool:
    if entry.get("tenant_id") != tenant_id:
        return False
    stored = entry.get("permission")
    if not isinstance(stored, dict):
        return False
    expected = {
        "role": permission.role,
        "department": permission.department,
        "access_level": permission.access_level,
        "department_filter": permission.department_filter,
    }
    if stored != expected:
        return False
    expires_at = entry.get("expires_at")
    if not isinstance(expires_at, str):
        return False
    expiry = datetime.fromisoformat(expires_at)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry > datetime.now(timezone.utc)


def get_semantic_cache() -> SemanticCache | None:
    """Redis cache for the request. None means the query proceeds as a miss."""
    from app.config import get_settings
    from app.services.cache.store import redis_store

    store = redis_store()
    if store is None:
        return None
    return SemanticCache(store, get_settings())
