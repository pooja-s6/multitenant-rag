from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models.document import Document
from app.services.exceptions import IngestionError
from app.services.ingestion.embedding_service import DeterministicEmbeddingService, get_embedding_service
from app.vector_dimensions import EMBEDDING_VECTOR_DIMENSION
from tests.test_auth import PASSWORD, _create_tenant, _login

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "sample_documents"


class _FailingEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise IngestionError("embedding failed")


class _ShortEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0, 1.0, 2.0] for _ in texts]


def _auth(client: TestClient) -> str:
    _create_tenant(client, "northwind", "admin@northwind.example")
    return _login(client, "admin@northwind.example")


def _use_embedder(client: TestClient, embedder: object | None = None) -> None:
    client.app.dependency_overrides[get_embedding_service] = lambda: embedder or DeterministicEmbeddingService()


def _upload(client: TestClient, token: str, filename: str, content_type: str) -> dict:
    response = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (filename, (SAMPLES / filename).read_bytes(), content_type)},
        data={"tenant_id": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_upload_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/documents",
        files={"file": ("leave_policy.txt", b"Annual leave is 20 working days.", "text/plain")},
    )
    assert response.status_code == 401


def test_sample_documents_are_stored_with_embeddings(client: TestClient) -> None:
    _use_embedder(client)
    token = _auth(client)
    uploads = [
        ("employee_handbook.pdf", "application/pdf", "09:00 to 17:30"),
        ("leave_policy.txt", "text/plain", "20 working days"),
        ("security_policy.md", "text/markdown", "multi-factor authentication"),
        ("engineering_guide.pdf", "application/pdf", "code review"),
    ]
    for filename, content_type, phrase in uploads:
        body = _upload(client, token, filename, content_type)
        assert body["filename"] == filename
        assert body["chunk_count"] >= 1
        assert body["tenant_id"]
        assert any(phrase in chunk["content"] for chunk in body["chunks"])
        assert all(len(chunk["content"].strip()) > 0 for chunk in body["chunks"])
        assert "embedding" not in body

    listed = client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
    assert listed.status_code == 200
    assert len(listed.json()) == 4
    assert "embedding" not in listed.text

    db = SessionLocal()
    try:
        stored = db.scalar(select(func.count()).select_from(Document))
        assert stored == 4
        handbook = db.scalar(select(Document).where(Document.filename == "employee_handbook.pdf"))
        assert handbook is not None
        assert handbook.chunks[0].embedding is not None
        assert len(handbook.chunks[0].embedding) == EMBEDDING_VECTOR_DIMENSION
        assert handbook.chunks[0].chunk_metadata["filename"] == "employee_handbook.pdf"
        assert handbook.chunks[0].tenant_id == handbook.tenant_id
        page_numbers = {chunk.page_number for chunk in handbook.chunks}
        assert 1 in page_numbers and 2 in page_numbers
    finally:
        db.close()


def test_get_and_delete_stay_inside_the_tenant(client: TestClient) -> None:
    _use_embedder(client)
    token = _auth(client)
    uploaded = _upload(client, token, "leave_policy.txt", "text/plain")
    document_id = uploaded["id"]

    fetched = client.get(f"/api/documents/{document_id}", headers={"Authorization": f"Bearer {token}"})
    assert fetched.status_code == 200
    assert "20 working days" in fetched.text

    other = _create_tenant(client, "other", "admin@other.example", token)
    other_token = _login(client, "admin@other.example")
    hidden = client.get(f"/api/documents/{document_id}", headers={"Authorization": f"Bearer {other_token}"})
    missing_delete = client.delete(
        f"/api/documents/{document_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    other_list = client.get("/api/documents", headers={"Authorization": f"Bearer {other_token}"})
    assert hidden.status_code == 404
    assert missing_delete.status_code == 404
    assert other_list.json() == []
    assert other["id"] != uploaded["tenant_id"]

    deleted = client.delete(f"/api/documents/{document_id}", headers={"Authorization": f"Bearer {token}"})
    assert deleted.status_code == 204
    gone = client.get(f"/api/documents/{document_id}", headers={"Authorization": f"Bearer {token}"})
    assert gone.status_code == 404


def test_empty_and_unsupported_uploads_are_rejected(client: TestClient) -> None:
    _use_embedder(client)
    token = _auth(client)
    headers = {"Authorization": f"Bearer {token}"}
    empty = client.post("/api/documents", headers=headers, files={"file": ("empty.txt", b"", "text/plain")})
    blank = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("blank.txt", b" \n\n ", "text/plain")},
    )
    unsupported = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("notes.docx", b"hello", "application/octet-stream")},
    )
    assert empty.status_code == 400
    assert blank.status_code == 400
    assert unsupported.status_code == 400
    assert client.get("/api/documents", headers=headers).json() == []


def test_failed_embedding_does_not_leave_a_document(client: TestClient) -> None:
    _use_embedder(client, _FailingEmbedder())
    token = _auth(client)
    response = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("leave_policy.txt", (SAMPLES / "leave_policy.txt").read_bytes(), "text/plain")},
    )
    assert response.status_code == 500
    listed = client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
    assert listed.json() == []


def test_wrong_embedding_width_is_rejected_before_save(client: TestClient) -> None:
    _use_embedder(client, _ShortEmbedder())
    token = _auth(client)
    response = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("leave_policy.txt", (SAMPLES / "leave_policy.txt").read_bytes(), "text/plain")},
    )
    assert response.status_code == 500
    assert client.get("/api/documents", headers={"Authorization": f"Bearer {token}"}).json() == []


def test_embedding_service_rejects_a_dimension_that_does_not_match_the_column(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_DIMENSION", "128")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(IngestionError):
            get_embedding_service()
    finally:
        get_settings.cache_clear()
