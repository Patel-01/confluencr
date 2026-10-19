from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum


class TransactionStatus(StrEnum):
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"


@dataclass
class Transaction:
    transaction_id: str
    source_account: str
    destination_account: str
    amount: Decimal
    currency: str
    status: TransactionStatus
    created_at: datetime
    processed_at: datetime | None = None

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
        normalized_id = transaction_id.strip()
        normalized_source = source_account.strip()
        normalized_destination = destination_account.strip()
        normalized_currency = currency.strip().upper()

        if not normalized_id:
            raise ValueError("transaction_id must not be empty")
        if not normalized_source or not normalized_destination:
            raise ValueError("account identifiers must not be empty")
        if amount <= 0:
            raise ValueError("amount must be greater than zero")
        if len(normalized_currency) != 3 or not normalized_currency.isalpha():
            raise ValueError("currency must be a three-letter code")

        return cls(
            transaction_id=normalized_id,
            source_account=normalized_source,
            destination_account=normalized_destination,
            amount=amount,
            currency=normalized_currency,
            status=TransactionStatus.PROCESSING,
            created_at=created_at or datetime.now(UTC),
        )

    def mark_processed(self, processed_at: datetime | None = None) -> None:
        if self.status is TransactionStatus.PROCESSED:
            return
        self.status = TransactionStatus.PROCESSED
        self.processed_at = processed_at or datetime.now(UTC)

