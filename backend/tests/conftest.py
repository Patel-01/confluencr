from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from confluencr.core.config import Settings
from confluencr.presentation.app import create_app


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "test.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        processing_delay_seconds=0,
        worker_max_workers=2,
    )
    migration_config = Config("alembic.ini")
    migration_config.attributes["database_url"] = settings.database_url
    command.upgrade(migration_config, "head")
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client

