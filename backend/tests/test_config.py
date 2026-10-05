import pytest
from pydantic import ValidationError

from app.config import DEV_JWT_SECRET, Settings, get_settings


def test_production_rejects_placeholder_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", DEV_JWT_SECRET)
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        get_settings()


def test_similarity_threshold_must_be_between_zero_and_one() -> None:
    with pytest.raises(ValidationError):
        Settings(cache_similarity_threshold=1.5)
