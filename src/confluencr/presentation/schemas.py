from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from confluencr.domain.transaction import Transaction


class TransactionWebhookRequest(BaseModel):
    transaction_id: str = Field(min_length=1, max_length=255)
    source_account: str = Field(min_length=1, max_length=255)
    destination_account: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized.isalpha():
            raise ValueError("currency must contain only letters")
        return normalized

    def to_domain(self) -> Transaction:
        return Transaction.start(**self.model_dump())


class WebhookAcceptedResponse(BaseModel):
    status: str = "ACCEPTED"
    transaction_id: str


class TransactionResponse(BaseModel):
    transaction_id: str
    source_account: str
    destination_account: str
    amount: Decimal
    currency: str
    status: str
    created_at: datetime
    processed_at: datetime | None

    @classmethod
    def from_domain(cls, transaction: Transaction) -> "TransactionResponse":
        return cls(
            transaction_id=transaction.transaction_id,
            source_account=transaction.source_account,
            destination_account=transaction.destination_account,
            amount=transaction.amount,
            currency=transaction.currency,
            status=transaction.status,
            created_at=transaction.created_at,
            processed_at=transaction.processed_at,
        )


class HealthResponse(BaseModel):
    status: str
    current_time: datetime

