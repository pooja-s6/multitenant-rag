from fastapi.testclient import TestClient

from app.main import create_app


def test_live_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


def test_live_keeps_client_request_id() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health/live", headers={"X-Request-ID": "req-phase1"})
    assert response.headers["x-request-id"] == "req-phase1"


def test_ready_reports_dependencies_without_leaking_errors() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health/ready")
    body = response.json()
    assert response.status_code in (200, 503)
    assert set(body["checks"]) == {"database", "redis"}
    for check in body["checks"].values():
        assert "password" not in check["detail"].lower()
        assert "://" not in check["detail"]
    if response.status_code == 503:
        assert body["status"] == "degraded"
