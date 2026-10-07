import json
from urllib.error import URLError

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models.query_log import QueryLog
from app.services.exceptions import BadGateway, BadRequest
from app.services.ingestion.embedding_service import DeterministicEmbeddingService, get_embedding_service
from app.services.rag.providers import (
    FakeLLMProvider,
    OpenAICompatibleProvider,
    get_llm_provider,
    provider_for,
)
from tests.test_auth import PASSWORD, _create_tenant, _login

LEAVE = "Employees receive 20 working days of annual leave each year."
SECRET = "The private salary band is 90000."


def _use_fakes(client: TestClient) -> None:
    settings = get_settings()
    client.app.dependency_overrides[get_embedding_service] = lambda: DeterministicEmbeddingService()
    client.app.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider(settings.small_model)


def _admin_and_user(client: TestClient) -> tuple[str, str]:
    _create_tenant(client, "northwind", "admin@northwind.example")
    admin = _login(client, "admin@northwind.example")
    created = client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {admin}"},
        json={"email": "user@northwind.example", "password": PASSWORD, "role": "USER"},
    )
    assert created.status_code == 201, created.text
    return admin, _login(client, "user@northwind.example")


def _upload(client: TestClient, token: str, filename: str, text: str, **form: str) -> dict:
    response = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (filename, text.encode(), "text/plain")},
        data=form,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _ask(client: TestClient, token: str, query: str, request_id: str = "req-phase-5") -> object:
    return client.post(
        "/api/rag/query",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": request_id},
        json={"query": query, "similarity_threshold": 0.99},
    )


def test_query_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/rag/query", json={"query": LEAVE})
    assert response.status_code == 401


def test_answer_cites_the_allowed_document_and_writes_a_log(client: TestClient) -> None:
    _use_fakes(client)
    admin, user = _admin_and_user(client)
    uploaded = _upload(client, admin, "leave_policy.txt", LEAVE, access_level="public")

    response = _ask(client, user, f"  {LEAVE}  ")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cache_hit"] is False
    assert body["model_used"] == get_settings().small_model
    assert body["request_id"] == "req-phase-5"
    assert body["latency"] >= 0
    assert "20 working days" in body["answer"]
    assert body["sources"][0]["filename"] == "leave_policy.txt"
    assert body["sources"][0]["document_id"] == uploaded["id"]
    assert "embedding" not in response.text

    db = SessionLocal()
    try:
        row = db.scalar(select(QueryLog).where(QueryLog.request_id == "req-phase-5"))
        assert row is not None
        assert row.cache_hit is False
        assert row.model == get_settings().small_model
        assert row.retrieved_chunk_count == 1
        assert float(row.estimated_cost) > 0
        assert row.sources[0]["filename"] == "leave_policy.txt"
    finally:
        db.close()


def test_private_and_other_tenant_text_stays_out_of_the_answer(client: TestClient) -> None:
    _use_fakes(client)
    admin, user = _admin_and_user(client)
    _upload(client, admin, "secret.txt", SECRET, access_level="private", allowed_roles="ADMIN")
    _create_tenant(client, "other", "admin@other.example", admin)
    other = _login(client, "admin@other.example")
    _upload(client, other, "foreign.txt", LEAVE, access_level="public")

    hidden = _ask(client, user, SECRET, request_id="req-private")
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["sources"] == []
    assert "90000" not in hidden.json()["answer"]
    assert hidden.json()["cache_hit"] is False

    visible = _ask(client, admin, SECRET, request_id="req-admin")
    assert "90000" in visible.json()["answer"]
    assert visible.json()["sources"][0]["filename"] == "secret.txt"

    cross = _ask(client, user, LEAVE, request_id="req-cross")
    assert cross.json()["sources"] == []
    assert "20 working days" not in cross.json()["answer"]


def test_blank_query_is_rejected(client: TestClient) -> None:
    _use_fakes(client)
    _admin_and_user(client)
    token = _login(client, "admin@northwind.example")
    response = _ask(client, token, "   ")
    assert response.status_code == 400


def test_empty_api_key_selects_the_fake_provider() -> None:
    settings = Settings(
        llm_provider="openai",
        llm_api_key="",
        small_model="gpt-4o-mini",
    )
    assert isinstance(provider_for(settings), FakeLLMProvider)


def test_openai_provider_reads_a_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "model": "gpt-4o-mini",
        "choices": [{"message": {"content": "Employees receive 20 working days."}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 5},
    }

    class _Response:
        def read(self) -> bytes:
            return json.dumps(payload).encode()

        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: _Response())
    provider = OpenAICompatibleProvider(model_name="gpt-4o-mini", api_key="test-key", base_url="https://example.invalid/v1")
    result = provider.complete(system="system", user="user", chunks=[])
    assert result.answer == "Employees receive 20 working days."
    assert result.input_tokens == 12
    assert result.output_tokens == 5
    assert result.model == "gpt-4o-mini"


def test_openai_provider_hides_transport_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail(request: object, timeout: float) -> object:
        raise URLError("offline")

    monkeypatch.setattr("urllib.request.urlopen", _fail)
    provider = OpenAICompatibleProvider(model_name="gpt-4o-mini", api_key="test-key", base_url="https://example.invalid/v1")
    with pytest.raises(BadGateway):
        provider.complete(system="system", user="user", chunks=[])


def test_unknown_provider_is_rejected() -> None:
    settings = Settings(llm_provider="other", llm_api_key="present", small_model="gpt-4o-mini")
    with pytest.raises(BadRequest):
        provider_for(settings)


def test_preprocess_rejects_an_empty_question() -> None:
    from app.services.rag.preprocess import preprocess_query

    with pytest.raises(BadRequest):
        preprocess_query(" \n\t ")
    assert preprocess_query("  annual   leave  ") == "annual leave"
