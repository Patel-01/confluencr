import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from confluencr.core.database import create_session_factory
from confluencr.domain.transaction import Transaction
from confluencr.infrastructure.persistence.repositories import (
    SqlAlchemySessionRepository,
    SqlAlchemyTransactionRepository,
)

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="set TEST_POSTGRES_URL to a disposable PostgreSQL database to run integration tests",
)


def test_postgres_migrations_and_concurrent_session_count() -> None:
    assert POSTGRES_URL is not None
    schema = f"confluencr_test_{uuid4().hex}"
    admin_engine = create_engine(POSTGRES_URL)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    test_url = make_url(POSTGRES_URL).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    )
    engine = create_engine(test_url)
    try:
        migration_config = Config("alembic.ini")
        migration_config.attributes["database_url"] = str(test_url)
        command.upgrade(migration_config, "head")

        session_factory = create_session_factory(engine)
        session_id = str(uuid4())
        request_count = 30

        def record_call(index: int) -> None:
            repository = SqlAlchemySessionRepository(session_factory())
            try:
                repository.record_api_call(
                    session_id, "GET", f"/v1/check/{index}", status_code=200
                )
            finally:
                repository.close()

        with ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(record_call, range(request_count)))

        repository = SqlAlchemySessionRepository(session_factory())
        try:
            summary = repository.get_summary(session_id)
        finally:
            repository.close()

        assert summary.total_api_calls == request_count

        transaction_id = f"txn_{uuid4().hex}"
        transaction = Transaction.start(
            transaction_id=transaction_id,
            source_account="source",
            destination_account="destination",
            amount=Decimal("12.34"),
            currency="INR",
        )
        writer = SqlAlchemyTransactionRepository(session_factory())
        try:
            assert writer.create_if_absent(transaction)
        finally:
            writer.close()

        now = datetime.now(UTC)

        def claim() -> str | None:
            repository = SqlAlchemyTransactionRepository(session_factory())
            try:
                return repository.claim_for_processing(
                    transaction_id, now=now, lease_until=now + timedelta(minutes=2)
                )
            finally:
                repository.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            tokens = list(executor.map(lambda _index: claim(), range(2)))
        assert sum(token is not None for token in tokens) == 1

        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert revision == "0002_durable_retries"
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()
