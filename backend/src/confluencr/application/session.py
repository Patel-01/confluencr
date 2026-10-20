import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from confluencr.domain.repositories import SessionRepository
from confluencr.domain.session import SessionSummary

logger = logging.getLogger(__name__)


class SessionAnalyticsService:
    """Tracks anonymous browser activity without coupling analytics to HTTP."""

    def __init__(
        self,
        repository_factory: Callable[[], SessionRepository],
        max_workers: int,
    ) -> None:
        self._repository_factory = repository_factory
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="session-analytics",
        )

    def record_api_call_async(
        self,
        session_id: str,
        method: str,
        path: str,
        status_code: int,
    ) -> None:
        self._executor.submit(
            self._record_api_call,
            session_id,
            method,
            path,
            status_code,
        )

    def get_summary(self, session_id: str) -> SessionSummary:
        repository = self._repository_factory()
        try:
            return repository.get_summary(session_id)
        finally:
            repository.close()

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)

    def _record_api_call(
        self,
        session_id: str,
        method: str,
        path: str,
        status_code: int,
    ) -> None:
        repository = self._repository_factory()
        try:
            repository.record_api_call(session_id, method, path, status_code)
        except Exception:
            logger.exception("Failed to record session activity for %s", session_id)
        finally:
            repository.close()
