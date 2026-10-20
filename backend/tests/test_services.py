from datetime import datetime

from confluencr.application.services import TransactionProcessingService
from confluencr.domain.transaction import Transaction, TransactionStatus


class FailingRepository:
    def __init__(self, *, fail_processing: bool) -> None:
        self.fail_processing = fail_processing
        self.failed = False
        self.closed = False
        self.token = "lease-1"

    def list_runnable(self, now: datetime) -> list[str]:
        raise NotImplementedError

    def get(self, transaction_id: str) -> Transaction | None:
        raise NotImplementedError

    def list_processing(self) -> list[str]:
        raise NotImplementedError

    def create_if_absent(self, transaction: Transaction) -> bool:
        raise NotImplementedError

    def mark_processed(self, transaction_id: str, *, lease_token: str) -> Transaction | None:
        if self.fail_processing:
            raise RuntimeError("database unavailable")
        raise AssertionError("unexpected processing retry")

    def claim_for_processing(
        self, transaction_id: str, *, now: datetime, lease_until: datetime
    ) -> str | None:
        return self.token

    def record_failure(
        self,
        transaction_id: str,
        *,
        lease_token: str,
        error: str,
        max_attempts: int,
        retry_at: datetime,
    ) -> TransactionStatus | None:
        self.failed = True
        return TransactionStatus.FAILED

    def close(self) -> None:
        self.closed = True


def test_processing_failure_is_persisted_as_failed_after_closing_work_session() -> None:
    repositories: list[FailingRepository] = []

    def repository_factory() -> FailingRepository:
        repository = FailingRepository(fail_processing=not repositories)
        repositories.append(repository)
        return repository

    service = TransactionProcessingService(repository_factory, delay_seconds=0, max_attempts=1)

    service.process("txn_fails")

    assert len(repositories) == 2
    assert all(repository.closed for repository in repositories)
    assert repositories[1].failed
