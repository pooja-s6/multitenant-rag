from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models.access import AccessLevel
from app.models.document import Document, DocumentChunk
from app.models.permission import DocumentPermission
from app.schemas.auth import CurrentUser
from app.services.exceptions import BadRequest
from app.services.ingestion.embedding_service import DeterministicEmbeddingService, get_embedding_service
from app.services.retrieval import search as retrieval_search
from app.config import get_settings
from app.vector_dimensions import EMBEDDING_VECTOR_DIMENSION
from tests.test_auth import PASSWORD, _create_tenant, _login

QUERY = "annual leave allowance is 20 working days"


class _FixedEmbedder:
    def __init__(self, vector: list[float]) -> None:
        self.vector = vector

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [list(self.vector) for _ in texts]


def _axis(index: int, other: float = 0.0) -> list[float]:
    values = [0.0] * EMBEDDING_VECTOR_DIMENSION
    values[index] = 1.0
    if other:
        values[index + 1] = other
    norm = sum(value * value for value in values) ** 0.5
    return [value / norm for value in values]


def _use_embedder(client: TestClient, embedder: object | None = None) -> None:
    client.app.dependency_overrides[get_embedding_service] = lambda: embedder or DeterministicEmbeddingService()


def _auth_pair(client: TestClient) -> tuple[str, str]:
    _create_tenant(client, "northwind", "admin@northwind.example")
    admin = _login(client, "admin@northwind.example")
    created = client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {admin}"},
        json={
            "email": "user@northwind.example",
            "password": PASSWORD,
            "role": "USER",
            "department": "Engineering",
        },
    )
    assert created.status_code == 201, created.text
    manager = client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {admin}"},
        json={
            "email": "manager@northwind.example",
            "password": PASSWORD,
            "role": "MANAGER",
            "department": "Sales",
        },
    )
    assert manager.status_code == 201, manager.text
    return admin, _login(client, "user@northwind.example")


def _upload(
    client: TestClient,
    token: str,
    filename: str,
    text: str,
    *,
    access_level: str,
    department: str | None = None,
    allowed_roles: str | None = None,
) -> dict:
    form = {"access_level": access_level}
    if department is not None:
        form["department"] = department
    if allowed_roles is not None:
        form["allowed_roles"] = allowed_roles
    response = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (filename, text.encode(), "text/plain")},
        data=form,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _search(client: TestClient, token: str, query: str, **extra: object) -> dict:
    response = client.post(
        "/api/retrieval/search",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": query, **extra},
    )
    return response


def test_search_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/retrieval/search", json={"query": QUERY})
    assert response.status_code == 401


def test_same_text_is_found_only_inside_the_caller_tenant(client: TestClient) -> None:
    _use_embedder(client)
    admin, user = _auth_pair(client)
    own = _upload(client, admin, "leave_policy.txt", QUERY, access_level="public")
    _create_tenant(client, "other", "admin@other.example", admin)
    other_token = _login(client, "admin@other.example")
    _upload(client, other_token, "leave_policy.txt", QUERY, access_level="public")

    found = _search(client, user, QUERY)
    assert found.status_code == 200, found.text
    chunks = found.json()["chunks"]
    assert len(chunks) == 1
    assert chunks[0]["document_id"] == own["id"]
    assert chunks[0]["filename"] == "leave_policy.txt"
    assert "20 working days" in chunks[0]["content"]
    assert chunks[0]["score"] == pytest.approx(1.0, abs=1e-6)
    assert "embedding" not in chunks[0]


def test_user_cannot_read_a_nearer_private_chunk(client: TestClient) -> None:
    _use_embedder(client)
    admin, user = _auth_pair(client)
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin}"})
    tenant_id = me.json()["tenant_id"]
    user_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {user}"})
    query_vector = _axis(0)
    farther = _axis(0, other=0.75)
    db = SessionLocal()
    try:
        private = _store_chunk(
            db,
            tenant_id=tenant_id,
            uploaded_by=me.json()["user_id"],
            filename="secret.txt",
            content="private salary bands",
            embedding=query_vector,
            access_level=AccessLevel.PRIVATE,
            department=None,
            allowed_roles=["ADMIN"],
        )
        public = _store_chunk(
            db,
            tenant_id=tenant_id,
            uploaded_by=me.json()["user_id"],
            filename="handbook.txt",
            content="public holiday list",
            embedding=farther,
            access_level=AccessLevel.PUBLIC,
            department=None,
            allowed_roles=["ADMIN", "MANAGER", "USER"],
        )
        other = _create_tenant(client, "other", "admin@other.example", admin)
        _store_chunk(
            db,
            tenant_id=other["id"],
            uploaded_by=None,
            filename="foreign.txt",
            content="other tenant secret",
            embedding=query_vector,
            access_level=AccessLevel.PUBLIC,
            department=None,
            allowed_roles=["ADMIN", "MANAGER", "USER"],
        )
        caller = CurrentUser(
            user_id=uuid4(),
            tenant_id=user_me.json()["tenant_id"],
            role="USER",
            email="user@northwind.example",
            department="Engineering",
        )
        visible = retrieval_search.search(
            db,
            caller,
            query="ignored because the embedder is fixed",
            settings=get_settings(),
            embedder=_FixedEmbedder(query_vector),
        )
        public_id = str(public.id)
        private_id = str(private.id)
    finally:
        db.close()

    assert [row.document_id for row in visible] == [public_id]
    assert private_id not in {row.document_id for row in visible}
    assert visible[0].score == pytest.approx(0.8, abs=1e-6)


def test_role_and_department_rules(client: TestClient) -> None:
    _use_embedder(client)
    admin, _user = _auth_pair(client)
    manager = _login(client, "manager@northwind.example")
    _upload(
        client,
        admin,
        "engineering.txt",
        "engineering onboarding",
        access_level="internal",
        department="Engineering",
    )
    _upload(client, admin, "sales.txt", "sales targets", access_level="internal", department="Sales")
    _upload(client, admin, "private.txt", "board notes", access_level="private", allowed_roles="ADMIN")

    manager_hits = _search(client, manager, "sales targets", similarity_threshold=0.99)
    assert manager_hits.status_code == 200
    assert [row["filename"] for row in manager_hits.json()["chunks"]] == ["sales.txt"]

    hidden = _search(client, manager, "engineering onboarding", similarity_threshold=0.99)
    assert hidden.json()["chunks"] == []
    board = _search(client, manager, "board notes", similarity_threshold=0.99)
    assert board.json()["chunks"] == []

    admin_hits = _search(client, admin, "engineering onboarding", similarity_threshold=0.99)
    assert [row["filename"] for row in admin_hits.json()["chunks"]] == ["engineering.txt"]
    narrowed = _search(client, admin, "engineering onboarding", department="Sales", similarity_threshold=0.99)
    assert narrowed.json()["chunks"] == []


def test_request_cannot_widen_top_k_or_threshold(client: TestClient) -> None:
    _use_embedder(client)
    admin, _user = _auth_pair(client)
    too_many = _search(client, admin, QUERY, top_k=get_settings().retrieval_top_k + 1)
    too_loose = _search(client, admin, QUERY, similarity_threshold=0.01)
    assert too_many.status_code == 400
    assert too_loose.status_code == 400


def test_low_similarity_is_excluded(client: TestClient) -> None:
    admin_body = _create_tenant(client, "northwind", "admin@northwind.example")
    admin = _login(client, "admin@northwind.example")
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin}"})
    db = SessionLocal()
    try:
        _store_chunk(
            db,
            tenant_id=me.json()["tenant_id"],
            uploaded_by=me.json()["user_id"],
            filename="unrelated.txt",
            content="unrelated",
            embedding=_axis(3),
            access_level=AccessLevel.PUBLIC,
            department=None,
            allowed_roles=["ADMIN", "MANAGER", "USER"],
        )
        caller = CurrentUser(
            user_id=me.json()["user_id"],
            tenant_id=admin_body["id"],
            role="ADMIN",
            email="admin@northwind.example",
            department=None,
        )
        visible = retrieval_search.search(
            db,
            caller,
            query="something else",
            settings=get_settings(),
            embedder=_FixedEmbedder(_axis(0)),
        )
    finally:
        db.close()
    assert visible == []


def test_blank_query_is_rejected() -> None:
    with pytest.raises(BadRequest):
        retrieval_search.search(
            None,  # type: ignore[arg-type]
            CurrentUser(
                user_id=uuid4(),
                tenant_id=uuid4(),
                role="USER",
                email="user@northwind.example",
            ),
            query="   ",
            settings=get_settings(),
            embedder=_FixedEmbedder(_axis(0)),
        )


def _store_chunk(
    db,
    *,
    tenant_id: str,
    uploaded_by: str | None,
    filename: str,
    content: str,
    embedding: list[float],
    access_level: AccessLevel,
    department: str | None,
    allowed_roles: list[str],
) -> Document:
    document = Document(
        tenant_id=tenant_id,
        filename=filename,
        content_type="text/plain",
        uploaded_by=uploaded_by,
        file_size=len(content),
    )
    db.add(document)
    db.flush()
    db.add(
        DocumentPermission(
            document_id=document.id,
            tenant_id=tenant_id,
            department=department,
            access_level=access_level,
            allowed_roles=allowed_roles,
        )
    )
    db.add(
        DocumentChunk(
            document_id=document.id,
            tenant_id=tenant_id,
            chunk_index=0,
            content=content,
            page_number=None,
            embedding=embedding,
            access_level=access_level,
            department=department,
            allowed_roles=allowed_roles,
            chunk_metadata={"filename": filename, "content_type": "text/plain"},
        )
    )
    db.commit()
    return document
