import time
from typing import Protocol

from redis import Redis
from redis.exceptions import RedisError


class CacheStore(Protocol):
    def get(self, key: str) -> str | None:
        """Return the stored string, or None when the key is missing or expired."""

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Store a string that expires after ttl_seconds."""

    def keys(self, prefix: str) -> list[str]:
        """Return keys that start with prefix."""

    def delete(self, key: str) -> None:
        """Remove one key."""

    def add_float(self, key: str, amount: float) -> None:
        """Add amount to a numeric counter."""

    def read_float(self, key: str) -> float:
        """Return a numeric counter, or zero when it is missing."""


class MemoryCacheStore:
    """Process-local store with the same expiry behavior as Redis. Used by tests."""

    def __init__(self) -> None:
        self._values: dict[str, tuple[str, float]] = {}
        self._counters: dict[str, float] = {}

    def get(self, key: str) -> str | None:
        item = self._values.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at <= time.monotonic():
            self._values.pop(key, None)
            return None
        return value

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._values[key] = (value, time.monotonic() + ttl_seconds)

    def keys(self, prefix: str) -> list[str]:
        return [key for key in list(self._values) if key.startswith(prefix) and self.get(key) is not None]

    def delete(self, key: str) -> None:
        self._values.pop(key, None)

    def add_float(self, key: str, amount: float) -> None:
        self._counters[key] = self._counters.get(key, 0.0) + amount

    def read_float(self, key: str) -> float:
        return self._counters.get(key, 0.0)


class RedisCacheStore:
    def __init__(self, url: str) -> None:
        self._client = Redis.from_url(url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)

    def get(self, key: str) -> str | None:
        value = self._client.get(key)
        return str(value) if value is not None else None

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._client.set(key, value, ex=ttl_seconds)

    def keys(self, prefix: str) -> list[str]:
        return [str(key) for key in self._client.scan_iter(match=f"{prefix}*", count=100)]

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def add_float(self, key: str, amount: float) -> None:
        self._client.incrbyfloat(key, amount)

    def read_float(self, key: str) -> float:
        value = self._client.get(key)
        return float(value) if value is not None else 0.0


def redis_store() -> CacheStore | None:
    """Return a Redis store, or None when Redis cannot be reached."""
    from app.config import get_settings

    store = RedisCacheStore(get_settings().redis_url)
    try:
        store.get("rag:cache:ping")
    except RedisError:
        return None
    return store
