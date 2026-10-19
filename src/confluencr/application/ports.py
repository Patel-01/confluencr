from typing import Protocol


class TransactionProcessor(Protocol):
    def submit(self, transaction_id: str) -> None: ...

