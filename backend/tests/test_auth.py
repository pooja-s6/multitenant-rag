from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import SessionLocal
from app.models.role import Role
from app.repositories import user_repository

PASSWORD = "correct-horse-1"


def _tenant_body(slug: str, email: str, name: str = "Acme") -> dict[str, str]:
    return {
        "name": name,
        "slug": slug,
        "admin_email": email,
        "admin_password": PASSWORD,
    }


def _create_tenant(client: TestClient, slug: str, email: str, token: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = client.post("/api/tenants", json=_tenant_body(slug, email), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, email: str, password: str = PASSWORD) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_login_returns_bearer_token(client: TestClient) -> None:
    _create_tenant(client, "acme", "admin@acme.example")
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@acme.example", "password": PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] == get_settings().access_token_expire_minutes * 60


def test_login_rejects_unknown_email_and_wrong_password_the_same_way(client: TestClient) -> None:
    _create_tenant(client, "acme", "admin@acme.example")
    unknown = client.post(
        "/api/auth/login",
        json={"email": "missing@acme.example", "password": PASSWORD},
    )
    wrong = client.post(
        "/api/auth/login",
        json={"email": "admin@acme.example", "password": "not-the-password"},
    )
    assert unknown.status_code == 401
    assert wrong.status_code == 401
    assert unknown.json() == wrong.json() == {"detail": "Invalid credentials"}


def test_password_is_stored_as_a_hash(client: TestClient) -> None:
    _create_tenant(client, "acme", "admin@acme.example")
    db = SessionLocal()
    try:
        user = user_repository.get_by_email(db, "admin@acme.example")
        assert user is not None
        assert user.password_hash != PASSWORD
        assert user.password_hash.startswith("$2")
    finally:
        db.close()


def test_me_requires_a_valid_token(client: TestClient) -> None:
    missing = client.get("/api/auth/me")
    malformed = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert missing.status_code == 401
    assert malformed.status_code == 401


def test_me_rejects_expired_and_tampered_tokens(client: TestClient) -> None:
    created = _create_tenant(client, "acme", "admin@acme.example")
    db = SessionLocal()
    try:
        user = user_repository.get_by_email(db, "admin@acme.example")
        assert user is not None
        user_id = user.id
    finally:
        db.close()
    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": str(user_id),
            "tenant_id": created["id"],
            "role": "ADMIN",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    expired_response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert expired_response.status_code == 401

    token = _login(client, "admin@acme.example")
    header, payload, signature = token.split(".")
    flipped = ("A" if signature[0] != "A" else "B") + signature[1:]
    tampered = ".".join((header, payload, flipped))
    tampered_response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert tampered_response.status_code == 401


def test_me_rejects_token_whose_tenant_does_not_match_the_user(client: TestClient) -> None:
    created = _create_tenant(client, "acme", "admin@acme.example")
    db = SessionLocal()
    try:
        user = user_repository.get_by_email(db, "admin@acme.example")
        assert user is not None
        user_id = user.id
    finally:
        db.close()

    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(user_id),
            "tenant_id": str(uuid4()),
            "role": "ADMIN",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_me_returns_database_identity(client: TestClient) -> None:
    created = _create_tenant(client, "acme", "admin@acme.example")
    token = _login(client, "admin@acme.example")
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == created["id"]
    assert body["role"] == "ADMIN"
    assert body["email"] == "admin@acme.example"
    assert body["user_id"]


def test_role_changes_in_the_database_apply_to_existing_tokens(client: TestClient) -> None:
    _create_tenant(client, "acme", "admin@acme.example")
    token = _login(client, "admin@acme.example")
    db = SessionLocal()
    try:
        user = user_repository.get_by_email(db, "admin@acme.example")
        assert user is not None
        user.role = Role.USER
        db.commit()
    finally:
        db.close()

    response = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
