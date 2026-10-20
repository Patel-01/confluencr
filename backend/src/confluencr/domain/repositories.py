from datetime import datetime
from typing import Protocol

from confluencr.domain.session import SessionSummary
from confluencr.domain.transaction import Transaction, TransactionStatus


class TransactionRepository(Protocol):
    def get(self, transaction_id: str) -> Transaction | None: ...

    def list_runnable(self, now: datetime) -> list[str]: ...

    def create_if_absent(self, transaction: Transaction) -> bool: ...

    def mark_processed(self, transaction_id: str, *, lease_token: str) -> Transaction | None: ...

    def claim_for_processing(
        self, transaction_id: str, *, now: datetime, lease_until: datetime
    ) -> str | None: ...

    def record_failure(
        self,
        transaction_id: str,
        *,
        lease_token: str,
        error: str,
        max_attempts: int,
        retry_at: datetime,
    ) -> TransactionStatus | None: ...

    def close(self) -> None: ...


class SessionRepository(Protocol):
    def record_api_call(
        self, session_id: str, method: str, path: str, status_code: int
    ) -> None: ...

    def get_summary(self, session_id: str) -> SessionSummary: ...

    def close(self) -> None: ...

