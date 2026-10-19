from collections.abc import Generator

import pytest
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
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client

