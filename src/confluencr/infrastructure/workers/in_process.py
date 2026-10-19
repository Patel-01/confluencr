from concurrent.futures import ThreadPoolExecutor

from confluencr.application.ports import TransactionProcessor
from confluencr.application.services import TransactionProcessingService


class InProcessTransactionProcessor(TransactionProcessor):
    """Local worker adapter; replace with a durable queue adapter for production."""

    def __init__(self, processing_service: TransactionProcessingService, max_workers: int) -> None:
        self._processing_service = processing_service
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="transactions"
        )

    def submit(self, transaction_id: str) -> None:
        self._executor.submit(self._processing_service.process, transaction_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)

