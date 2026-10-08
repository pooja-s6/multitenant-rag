import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.config import get_settings
from app.services.cache.semantic_cache import SemanticCache, get_semantic_cache, permission_context
from app.services.cache.store import MemoryCacheStore
from app.services.ingestion.embedding_service import DeterministicEmbeddingService, get_embedding_service
from app.services.rag.providers import FakeLLMProvider, get_llm_provider
from app.vector_dimensions import EMBEDDING_VECTOR_DIMENSION
from tests.test_auth import PASSWORD, _create_tenant, _login
from tests.test_rag import LEAVE, SECRET, _admin_and_user, _upload

class _CountingProvider:
    def __init__(self, model_name: str) -> None:
        self.inner = FakeLLMProvider(model_name)
        self.calls = 0

    def complete(self, *, system: str, user: str, chunks: list, model: str | None = None) -> object:
        self.calls += 1
        return self.inner.complete(system=system, user=user, chunks=chunks, model=model)


def _client_cache(client: TestClient) -> tuple[SemanticCache, _CountingProvider]:
    settings = get_settings()
    cache = SemanticCache(MemoryCacheStore(), settings)
    provider = _CountingProvider(settings.small_model)
    client.app.dependency_overrides[get_embedding_service] = lambda: DeterministicEmbeddingService()
    client.app.dependency_overrides[get_llm_provider] = lambda: provider
    client.app.dependency_overrides[get_semantic_cache] = lambda: cache
    return cache, provider


def _ask(client: TestClient, token: str, query: str, **extra: object):
    return client.post(
        "/api/rag/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "similarity_threshold": 0.99, **extra},
    )


def test_second_identical_question_is_a_cache_hit(client: TestClient) -> None:
    cache, provider = _client_cache(client)
    admin, _user = _admin_and_user(client)
    _upload(client, admin, "leave_policy.txt", LEAVE, access_level="public")

    first = _ask(client, admin, LEAVE)
    second = _ask(client, admin, LEAVE)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["cache_hit"] is False
    assert second.json()["cache_hit"] is True
    assert second.json()["answer"] == first.json()["answer"]
    assert second.json()["sources"][0]["filename"] == "leave_policy.txt"
    assert provider.calls == 1
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin}"}).json()
    stats = cache.stats(me["tenant_id"])
    assert stats.misses == 1
    assert stats.hits == 1
    assert stats.cost_saved > 0
    assert stats.latency_saved_ms > 0


def test_other_tenant_does_not_receive_the_cached_answer(client: TestClient) -> None:
    _cache, provider = _client_cache(client)
    admin, _user = _admin_and_user(client)
    _upload(client, admin, "leave_policy.txt", LEAVE, access_level="public")
    first = _ask(client, admin, LEAVE)
    assert first.json()["cache_hit"] is False

    _create_tenant(client, "other", "admin@other.example", admin)
    other = _login(client, "admin@other.example")
    second = _ask(client, other, LEAVE)
    assert second.status_code == 200, second.text
    assert second.json()["cache_hit"] is False
    assert provider.calls == 2
    assert "20 working days" not in second.json()["answer"]
    assert second.json()["sources"] == []


def test_other_permission_context_does_not_reuse_a_private_answer(client: TestClient) -> None:
    _cache, provider = _client_cache(client)
    admin, user = _admin_and_user(client)
    _upload(client, admin, "secret.txt", SECRET, access_level="private", allowed_roles="ADMIN")
    cached = _ask(client, admin, SECRET)
    assert cached.json()["cache_hit"] is False
    assert "90000" in cached.json()["answer"]

    hidden = _ask(client, user, SECRET)
    assert hidden.json()["cache_hit"] is False
    assert provider.calls == 2
    assert hidden.json()["sources"] == []
    assert "90000" not in hidden.json()["answer"]


def test_a_different_department_filter_is_a_miss(client: TestClient) -> None:
    _cache, provider = _client_cache(client)
    admin, _user = _admin_and_user(client)
    _upload(client, admin, "leave_policy.txt", LEAVE, access_level="public")
    _ask(client, admin, LEAVE)
    narrowed = _ask(client, admin, LEAVE, department="Sales")
    assert narrowed.json()["cache_hit"] is False
    assert provider.calls == 2


def test_lookup_rejects_expired_and_foreign_entries() -> None:
    settings = get_settings()
    store = MemoryCacheStore()
    cache = SemanticCache(store, settings)
    tenant = "tenant-a"
    permission = permission_context(role="USER", department=None, access_level=None, department_filter=None)
    vector = [0.0] * EMBEDDING_VECTOR_DIMENSION
    vector[0] = 1.0
    prefix = f"rag:cache:{tenant}:{permission.digest()}:"
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    foreign = _entry(tenant="tenant-b", permission=permission, embedding=vector, expires_at=None)
    expired = _entry(tenant=tenant, permission=permission, embedding=vector, expires_at=past)
    store.set(prefix + "foreign", json.dumps(foreign), settings.cache_ttl)
    store.set(prefix + "expired", json.dumps(expired), settings.cache_ttl)
    assert cache.lookup(tenant_id=tenant, permission=permission, embedding=vector) is None


def test_low_similarity_is_a_miss_and_the_context_is_bounded() -> None:
    settings = get_settings()
    store = MemoryCacheStore()
    cache = SemanticCache(store, settings, max_entries=2)
    tenant = "tenant-a"
    permission = permission_context(role="ADMIN", department="Engineering", access_level="public", department_filter=None)
    near = _axis(0)
    far = _axis(1)
    cache.store(
        tenant_id=tenant,
        permission=permission,
        query="one",
        embedding=near,
        answer="first",
        sources=[],
        model="gpt-4o-mini",
        latency_ms=10,
        estimated_cost=0.01,
    )
    cache.store(
        tenant_id=tenant,
        permission=permission,
        query="two",
        embedding=near,
        answer="second",
        sources=[],
        model="gpt-4o-mini",
        latency_ms=10,
        estimated_cost=0.01,
    )
    cache.store(
        tenant_id=tenant,
        permission=permission,
        query="three",
        embedding=near,
        answer="third",
        sources=[],
        model="gpt-4o-mini",
        latency_ms=10,
        estimated_cost=0.01,
    )
    assert cache.lookup(tenant_id=tenant, permission=permission, embedding=far) is None
    hit = cache.lookup(tenant_id=tenant, permission=permission, embedding=near)
    assert hit is not None
    assert hit.answer in {"second", "third"}
    assert len(store.keys(f"rag:cache:{tenant}:{permission.digest()}:")) == 2


def _axis(index: int) -> list[float]:
    values = [0.0] * EMBEDDING_VECTOR_DIMENSION
    values[index] = 1.0
    return values


def _entry(tenant: str, permission, embedding: list[float], expires_at: str | None) -> dict:
    when = expires_at or (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    return {
        "tenant_id": tenant,
        "permission": {
            "role": permission.role,
            "department": permission.department,
            "access_level": permission.access_level,
            "department_filter": permission.department_filter,
        },
        "query": "stored",
        "embedding": embedding,
        "answer": "secret answer",
        "sources": [],
        "model": "gpt-4o-mini",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": when,
        "latency_ms": 5,
        "estimated_cost": 0.01,
    }
