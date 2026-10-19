from typing import Protocol

from confluencr.domain.session import SessionSummary
from confluencr.domain.transaction import Transaction


class TransactionRepository(Protocol):
    def get(self, transaction_id: str) -> Transaction | None: ...

    def list_processing(self) -> list[str]: ...

    def create_if_absent(self, transaction: Transaction) -> bool: ...

    def mark_processed(self, transaction_id: str) -> Transaction | None: ...

    def close(self) -> None: ...


class SessionRepository(Protocol):
    def record_api_call(
        self, session_id: str, method: str, path: str, status_code: int
    ) -> None: ...

    def get_summary(self, session_id: str) -> SessionSummary: ...

    def close(self) -> None: ...

