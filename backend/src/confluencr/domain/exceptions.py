class DomainError(Exception):
    """Base class for expected business rule violations."""


class TransactionNotFoundError(DomainError):
    def __init__(self, transaction_id: str) -> None:
        super().__init__(f"Transaction '{transaction_id}' was not found")
        self.transaction_id = transaction_id

