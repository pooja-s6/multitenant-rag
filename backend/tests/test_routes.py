from fastapi.testclient import TestClient

from app.main import create_app


def test_dashboard_requires_authentication() -> None:
    client = TestClient(create_app())
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 401
