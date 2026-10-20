import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event, Lock, Thread

from confluencr.application.ports import TransactionProcessor
from confluencr.application.services import TransactionProcessingService
from confluencr.domain.repositories import TransactionRepository

logger = logging.getLogger(__name__)


class InProcessTransactionProcessor(TransactionProcessor):
    """Runs jobs from the database-backed queue using local worker threads."""

    def __init__(
        self,
        processing_service: TransactionProcessingService,
        repository_factory: Callable[[], TransactionRepository],
        max_workers: int,
    ) -> None:
        self._processing_service = processing_service
        self._repository_factory = repository_factory
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="transactions"
        )
        self._stopping = Event()
        self._in_flight: set[str] = set()
        self._lock = Lock()
        self._scheduler: Thread | None = None

    def start(self) -> None:
        if self._scheduler is not None:
            return
        self._scheduler = Thread(
            target=self._poll_queue, name="transaction-queue-poller", daemon=True
        )
        self._scheduler.start()

    def submit(self, transaction_id: str) -> None:
        with self._lock:
            if transaction_id in self._in_flight:
                return
            self._in_flight.add(transaction_id)
        try:
            future = self._executor.submit(self._processing_service.process, transaction_id)
            future.add_done_callback(lambda _future: self._release(transaction_id))
        except RuntimeError:
            self._release(transaction_id)
            raise

    def _release(self, transaction_id: str) -> None:
        with self._lock:
            self._in_flight.discard(transaction_id)

    def _poll_queue(self) -> None:
        while not self._stopping.is_set():
            repository: TransactionRepository | None = None
            try:
                repository = self._repository_factory()
                for transaction_id in repository.list_runnable(datetime.now(UTC)):
                    self.submit(transaction_id)
            except Exception:
                logger.exception("Could not poll the persisted transaction queue")
            finally:
                if repository is not None:
                    repository.close()
            self._stopping.wait(1.0)

    def shutdown(self) -> None:
        self._stopping.set()
        if self._scheduler is not None:
            self._scheduler.join(timeout=5)
        self._executor.shutdown(wait=False, cancel_futures=False)

