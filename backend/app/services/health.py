import logging
from typing import Literal

from redis import Redis
from sqlalchemy import text

from app.config import get_settings
from app.database import engine
from app.schemas.health import DependencyCheck, LiveResponse, ReadyResponse

logger = logging.getLogger(__name__)


def liveness() -> LiveResponse:
    return LiveResponse(status="ok")


def readiness() -> ReadyResponse:
    checks = {
        "database": _check_database(),
        "redis": _check_redis(),
    }
    status: Literal["ok", "degraded"] = (
        "ok" if all(check.ok for check in checks.values()) else "degraded"
    )
    return ReadyResponse(status=status, checks=checks)


def _check_database() -> DependencyCheck:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.warning("database readiness check failed", exc_info=True)
        return DependencyCheck(ok=False, detail="unavailable")
    return DependencyCheck(ok=True, detail="connected")


def _check_redis() -> DependencyCheck:
    client = Redis.from_url(
        get_settings().redis_url,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        if not client.ping():
            return DependencyCheck(ok=False, detail="unavailable")
    except Exception:
        logger.warning("redis readiness check failed", exc_info=True)
        return DependencyCheck(ok=False, detail="unavailable")
    finally:
        client.close()
    return DependencyCheck(ok=True, detail="connected")
