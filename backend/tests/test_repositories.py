from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from confluencr.core.database import Base, create_database_engine, create_session_factory
from confluencr.domain.transaction import Transaction
from confluencr.infrastructure.persistence.repositories import SqlAlchemyTransactionRepository


def _transaction() -> Transaction:
    return Transaction.start(
        transaction_id="txn_integrity",
        source_account="source",
        destination_account="destination",
        amount=Decimal("1.00"),
        currency="INR",
    )


def test_create_if_absent_does_not_misreport_non_duplicate_integrity_error() -> None:
    session = MagicMock()
    session.commit.side_effect = IntegrityError("insert", {}, RuntimeError("constraint"))
    session.get.return_value = None
    repository = SqlAlchemyTransactionRepository(session)

    with pytest.raises(IntegrityError):
        repository.create_if_absent(_transaction())

    session.rollback.assert_called_once()
    session.get.assert_called_once()


def test_failed_retry_persists_terminal_status(tmp_path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'failed.sqlite3'}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repository = SqlAlchemyTransactionRepository(session_factory())
    transaction = _transaction()

    assert repository.create_if_absent(transaction)
    now = datetime.now(UTC)
    lease_token = repository.claim_for_processing(
        transaction.transaction_id, now=now, lease_until=now + timedelta(minutes=2)
    )
    assert lease_token is not None
    status = repository.record_failure(
        transaction.transaction_id,
        lease_token=lease_token,
        error="worker failed",
        max_attempts=1,
        retry_at=now + timedelta(seconds=1),
    )
    persisted = repository.get(transaction.transaction_id)
    repository.close()
    engine.dispose()

    assert status.value == "FAILED"
    assert persisted is not None
    assert persisted.status.value == "FAILED"


def test_persisted_queue_claims_once_and_retries_until_attempt_limit(tmp_path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'queue.sqlite3'}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    writer = SqlAlchemyTransactionRepository(session_factory())
    transaction = _transaction()
    now = datetime.now(UTC)
    retry_at = now + timedelta(seconds=5)

    assert writer.create_if_absent(transaction)
    lease_token = writer.claim_for_processing(
        transaction.transaction_id, now=now, lease_until=now + timedelta(minutes=2)
    )
    assert lease_token is not None
    assert writer.claim_for_processing(
        transaction.transaction_id, now=now, lease_until=now + timedelta(minutes=2)
    ) is None
    assert writer.list_runnable(now) == []

    assert writer.record_failure(
        transaction.transaction_id,
        lease_token=lease_token,
        error="temporary worker failure",
        max_attempts=2,
        retry_at=retry_at,
    ).value == "PROCESSING"
    assert writer.list_runnable(now) == []
    assert writer.list_runnable(retry_at) == [transaction.transaction_id]

    retry_lease_token = writer.claim_for_processing(
        transaction.transaction_id,
        now=retry_at,
        lease_until=retry_at + timedelta(minutes=2),
    )
    assert retry_lease_token is not None
    assert writer.record_failure(
        transaction.transaction_id,
        lease_token=retry_lease_token,
        error="retry exhausted",
        max_attempts=2,
        retry_at=retry_at + timedelta(seconds=10),
    ).value == "FAILED"
    assert writer.list_runnable(retry_at + timedelta(hours=1)) == []
    writer.close()
    engine.dispose()


def test_stale_worker_cannot_complete_or_fail_a_reclaimed_transaction(tmp_path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'fenced.sqlite3'}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repository = SqlAlchemyTransactionRepository(session_factory())
    transaction = _transaction()
    now = datetime.now(UTC)

    assert repository.create_if_absent(transaction)
    old_token = repository.claim_for_processing(
        transaction.transaction_id,
        now=now,
        lease_until=now + timedelta(seconds=1),
    )
    assert old_token is not None
    new_token = repository.claim_for_processing(
        transaction.transaction_id,
        now=now + timedelta(seconds=2),
        lease_until=now + timedelta(minutes=2),
    )
    assert new_token is not None and new_token != old_token

    assert repository.mark_processed(transaction.transaction_id, lease_token=old_token) is None
    assert (
        repository.record_failure(
            transaction.transaction_id,
            lease_token=old_token,
            error="late worker failure",
            max_attempts=3,
            retry_at=now + timedelta(minutes=3),
        )
        is None
    )
    assert repository.mark_processed(transaction.transaction_id, lease_token=new_token) is not None
    assert repository.get(transaction.transaction_id).status.value == "PROCESSED"
    repository.close()
    engine.dispose()
