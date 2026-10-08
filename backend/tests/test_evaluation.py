from fastapi.testclient import TestClient

from app.config import get_settings
from tests.test_rag import LEAVE, _admin_and_user, _ask, _upload, _use_fakes
from tests.test_routing import COMPLEX


def test_four_way_comparison_on_the_fake_provider(client: TestClient) -> None:
    """Plain RAG, cache, routing, and both, using the local provider.

    The fake provider echoes the top chunk, so this checks routing and reuse
    rather than answer quality against a human rubric.
    """
    _use_fakes(client)
    admin, _user = _admin_and_user(client)
    _upload(client, admin, "leave_policy.txt", LEAVE, access_level="public")
    _upload(client, admin, "comparison.txt", COMPLEX, access_level="public")
    settings = get_settings()

    plain = _ask(client, admin, LEAVE, request_id="eval-plain")
    cached = _ask(client, admin, LEAVE, request_id="eval-cache")
    routed = _ask(client, admin, COMPLEX, request_id="eval-route")
    both = _ask(client, admin, COMPLEX, request_id="eval-both")

    assert plain.status_code == 200, plain.text
    plain_body = plain.json()
    cached_body = cached.json()
    routed_body = routed.json()
    both_body = both.json()

    assert plain_body["cache_hit"] is False
    assert plain_body["model_used"] == settings.small_model
    assert "20 working days" in plain_body["answer"]

    assert cached_body["cache_hit"] is True
    assert cached_body["model_used"] == settings.small_model
    assert cached_body["answer"] == plain_body["answer"]

    assert routed_body["cache_hit"] is False
    assert routed_body["model_used"] == settings.large_model

    assert both_body["cache_hit"] is True
    assert both_body["model_used"] == settings.large_model
    assert both_body["answer"] == routed_body["answer"]
