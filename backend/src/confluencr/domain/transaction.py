from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum


class TransactionStatus(StrEnum):
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class Transaction:
    transaction_id: str
    source_account: str
    destination_account: str
    amount: Decimal
    currency: str
    status: TransactionStatus
    created_at: datetime
    processed_at: datetime | None = None

    def __post_init__(self) -> None:
        normalized_id = self.transaction_id.strip()
        normalized_source = self.source_account.strip()
        normalized_destination = self.destination_account.strip()
        normalized_currency = self.currency.strip().upper()
        if not normalized_id:
            raise ValueError("transaction_id must not be empty")
        if not normalized_source or not normalized_destination:
            raise ValueError("account identifiers must not be empty")
        if self.amount <= 0:
            raise ValueError("amount must be greater than zero")
        if len(normalized_currency) != 3 or not normalized_currency.isalpha():
            raise ValueError("currency must be a three-letter code")
        if not isinstance(self.status, TransactionStatus):
            raise ValueError("status must be a TransactionStatus")
        if (self.status is TransactionStatus.PROCESSED) != (self.processed_at is not None):
            raise ValueError("only processed transactions may have processed_at")

        object.__setattr__(self, "transaction_id", normalized_id)
        object.__setattr__(self, "source_account", normalized_source)
        object.__setattr__(self, "destination_account", normalized_destination)
        object.__setattr__(self, "currency", normalized_currency)

    @classmethod
    def start(
        cls,
        *,
        transaction_id: str,
        source_account: str,
        destination_account: str,
        amount: Decimal,
        currency: str,
        created_at: datetime | None = None,
    ) -> "Transaction":
        return cls(
            transaction_id=transaction_id,
            source_account=source_account,
            destination_account=destination_account,
            amount=amount,
            currency=currency,
            status=TransactionStatus.PROCESSING,
            created_at=created_at or datetime.now(UTC),
        )

    def mark_processed(self, processed_at: datetime | None = None) -> "Transaction":
        if self.status is not TransactionStatus.PROCESSING:
            return self
        return replace(
            self,
            status=TransactionStatus.PROCESSED,
            processed_at=processed_at or datetime.now(UTC),
        )

    def mark_failed(self) -> "Transaction":
        if self.status is not TransactionStatus.PROCESSING:
            return self
        return replace(self, status=TransactionStatus.FAILED)

