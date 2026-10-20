import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from confluencr.application.ports import TransactionProcessor
from confluencr.domain.exceptions import TransactionNotFoundError
from confluencr.domain.repositories import TransactionRepository
from confluencr.domain.transaction import Transaction, TransactionStatus

logger = logging.getLogger(__name__)


class TransactionApplicationService:
    """Coordinates transaction use cases without knowing transport or storage details."""

    def __init__(self, repository: TransactionRepository, processor: TransactionProcessor) -> None:
        self._repository = repository
        self._processor = processor

    def receive_webhook(self, transaction: Transaction) -> bool:
        created = self._repository.create_if_absent(transaction)
        if created:
            self._processor.submit(transaction.transaction_id)
        return created

    def get_transaction(self, transaction_id: str) -> Transaction:
        transaction = self._repository.get(transaction_id)
        if transaction is None:
            raise TransactionNotFoundError(transaction_id)
        return transaction


class TransactionProcessingService:
    """Executes the transaction's long-running processing workflow."""

    def __init__(
        self,
        repository_factory: Callable[[], TransactionRepository],
        delay_seconds: float,
        lease_seconds: int = 120,
        max_attempts: int = 3,
        retry_delay_seconds: float = 2.0,
    ) -> None:
        self._repository_factory = repository_factory
        self._delay_seconds = delay_seconds
        self._effective_lease_seconds = max(lease_seconds, int(delay_seconds) + 30)
        self._max_attempts = max_attempts
        self._retry_delay_seconds = retry_delay_seconds

    def process(self, transaction_id: str) -> None:
        repository: TransactionRepository | None = None
        lease_token: str | None = None
        now = datetime.now(UTC)
        processing_error: str | None = None
        try:
            repository = self._repository_factory()
            lease_token = repository.claim_for_processing(
                transaction_id,
                now=now,
                lease_until=now + timedelta(seconds=self._effective_lease_seconds),
            )
            if lease_token is None:
                return
            time.sleep(self._delay_seconds)
            transaction = repository.mark_processed(transaction_id, lease_token=lease_token)
            if transaction is None:
                logger.info("Worker lease for transaction %s is no longer current", transaction_id)
        except Exception as error:
            logger.exception("Transaction processing failed for %s", transaction_id)
            processing_error = str(error)
        finally:
            if repository is not None:
                repository.close()
        if processing_error is not None and lease_token is not None:
            self._record_failure(transaction_id, lease_token, processing_error)

    def _record_failure(self, transaction_id: str, lease_token: str, error: str) -> None:
        repository: TransactionRepository | None = None
        try:
            repository = self._repository_factory()
            status = repository.record_failure(
                transaction_id,
                lease_token=lease_token,
                error=error,
                max_attempts=self._max_attempts,
                retry_at=datetime.now(UTC) + timedelta(seconds=self._retry_delay_seconds),
            )
            if status is None:
                logger.info(
                    "Failure result for %s was ignored because its lease expired", transaction_id
                )
            elif status is TransactionStatus.FAILED:
                logger.error("Transaction %s exhausted processing retries", transaction_id)
            else:
                logger.info("Transaction %s is scheduled for retry", transaction_id)
        except Exception:
            logger.exception("Could not persist retry state for %s", transaction_id)
        finally:
            if repository is not None:
                repository.close()

