import logging
import time
from collections.abc import Callable

from confluencr.application.ports import TransactionProcessor
from confluencr.domain.exceptions import TransactionNotFoundError
from confluencr.domain.repositories import TransactionRepository
from confluencr.domain.transaction import Transaction

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
    ) -> None:
        self._repository_factory = repository_factory
        self._delay_seconds = delay_seconds

    def process(self, transaction_id: str) -> None:
        repository: TransactionRepository | None = None
        try:
            time.sleep(self._delay_seconds)
            repository = self._repository_factory()
            transaction = repository.mark_processed(transaction_id)
            if transaction is None:
                logger.warning("Transaction %s disappeared before processing", transaction_id)
        except Exception:
            logger.exception("Transaction processing failed for %s", transaction_id)
        finally:
            if repository is not None:
                repository.close()

