import json
import logging

from fastapi.testclient import TestClient

from app.config import get_settings
from app.services.analytics.summary import _percentile
from app.utils.logging import JsonFormatter
from tests.test_auth import _create_tenant, _login
from tests.test_rag import LEAVE, _admin_and_user, _ask, _upload, _use_fakes


def test_summary_matches_query_logs_for_the_caller_tenant(client: TestClient) -> None:
    _use_fakes(client)
    admin, user = _admin_and_user(client)
    _upload(client, admin, "leave_policy.txt", LEAVE, access_level="public")
    _ask(client, user, LEAVE, request_id="dash-1")
    _ask(client, user, LEAVE, request_id="dash-2")

    user_summary = client.get("/api/dashboard/summary", headers={"Authorization": f"Bearer {user}"})
    admin_summary = client.get("/api/dashboard/summary", headers={"Authorization": f"Bearer {admin}"})
    assert user_summary.status_code == 200, user_summary.text
    assert admin_summary.status_code == 200, admin_summary.text
    user_body = user_summary.json()
    admin_body = admin_summary.json()

    assert user_body["total_queries"] == 2
    assert user_body["cache_hits"] == 1
    assert user_body["cache_misses"] == 1
    assert user_body["hit_rate"] == 0.5
    assert user_body["average_latency_ms"] >= 0
    assert user_body["p95_latency_ms"] >= 0
    assert user_body["estimated_cost"] > 0
    assert user_body["estimated_cost_saved"] > 0
    assert user_body["input_tokens"] > 0
    assert user_body["queries_by_tenant"] is None
    assert user_body["model_distribution"][0]["model"] == get_settings().small_model
    assert admin_body["total_queries"] == 2
    assert admin_body["queries_by_tenant"][0]["tenant_id"] == admin_body["tenant_id"]
    assert admin_body["queries_by_tenant"][0]["total_queries"] == 2


def test_another_tenant_does_not_change_the_summary(client: TestClient) -> None:
    _use_fakes(client)
    admin, user = _admin_and_user(client)
    _upload(client, admin, "leave_policy.txt", LEAVE, access_level="public")
    _ask(client, user, LEAVE, request_id="own-1")
    before = client.get("/api/dashboard/summary", headers={"Authorization": f"Bearer {user}"}).json()

    _create_tenant(client, "other", "admin@other.example", admin)
    other = _login(client, "admin@other.example")
    _upload(client, other, "foreign.txt", LEAVE, access_level="public")
    _ask(client, other, LEAVE, request_id="other-1")

    after = client.get("/api/dashboard/summary", headers={"Authorization": f"Bearer {user}"}).json()
    other_body = client.get("/api/dashboard/summary", headers={"Authorization": f"Bearer {other}"}).json()
    assert after["total_queries"] == before["total_queries"]
    assert other_body["total_queries"] == 1
    assert other_body["tenant_id"] != after["tenant_id"]


def test_p95_is_at_least_the_median() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 100.0]
    assert _percentile(values, 0.95) >= _percentile(values, 0.5)
    assert _percentile([], 0.95) == 0.0


def test_rag_log_is_json_with_the_required_fields() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="app.services.rag.pipeline",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="rag query",
        args=(),
        exc_info=None,
    )
    record.rag = {
        "request_id": "req-1",
        "tenant_id": "tenant-a",
        "user_id": "user-a",
        "latency_ms": 12.5,
        "model": "gpt-4o-mini",
        "cache_hit": False,
        "retrieved_chunk_count": 1,
        "estimated_cost": 0.001,
    }
    payload = json.loads(formatter.format(record))
    assert payload["request_id"] == "req-1"
    assert payload["tenant_id"] == "tenant-a"
    assert payload["cache_hit"] is False
    assert "password" not in payload
    assert "database_url" not in payload
