import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine.url import make_url

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://rag:rag@localhost:5432/rag_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.config import get_settings  # noqa: E402
from app.database import engine  # noqa: E402
from app.main import create_app  # noqa: E402

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _ensure_test_database() -> None:
    url = make_url(TEST_DATABASE_URL)
    admin_url = url.set(drivername="postgresql", database="rag")
    with psycopg.connect(admin_url.render_as_string(hide_password=False), autocommit=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (url.database,),
        ).fetchone()
        if exists is None:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(str(url.database))))


def _upgrade() -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("prepend_sys_path", str(BACKEND_ROOT))
    command.upgrade(config, "head")


def _truncate() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE query_logs, document_chunks, document_permissions, documents, users, tenants CASCADE"
            )
        )


@pytest.fixture(scope="session", autouse=True)
def _prepare_database() -> None:
    get_settings.cache_clear()
    _ensure_test_database()
    _upgrade()


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _clean_tables(_prepare_database: None) -> None:
    _truncate()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client
