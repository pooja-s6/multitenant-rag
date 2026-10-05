import pytest
from fastapi.testclient import TestClient

from app.main import create_app

PLACEHOLDER_ROUTES = [
    ("post", "/api/rag/query"),
    ("get", "/api/dashboard/summary"),
]


@pytest.mark.parametrize(("method", "path"), PLACEHOLDER_ROUTES)
def test_future_routes_are_registered_and_not_implemented(method: str, path: str) -> None:
    client = TestClient(create_app())
    response = client.request(method, path)
    assert response.status_code == 501
    assert "implemented in phase" in response.json()["detail"]
