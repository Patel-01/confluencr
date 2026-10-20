from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from confluencr.domain.transaction import Transaction, TransactionStatus


def test_transaction_factory_normalizes_values_and_transitions_immutably() -> None:
    transaction = Transaction.start(
        transaction_id=" txn_1 ",
        source_account=" source ",
        destination_account=" destination ",
        amount=Decimal("12.50"),
        currency="inr",
    )

    processed = transaction.mark_processed(datetime(2026, 1, 1, tzinfo=UTC))

    assert transaction.transaction_id == "txn_1"
    assert transaction.currency == "INR"
    assert transaction.status is TransactionStatus.PROCESSING
    assert processed.status is TransactionStatus.PROCESSED
    assert processed.processed_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert processed.mark_failed() is processed
    with pytest.raises(FrozenInstanceError):
        transaction.status = TransactionStatus.FAILED  # type: ignore[misc]


@pytest.mark.parametrize(
    "overrides",
    [
        {"transaction_id": " "},
        {"source_account": " "},
        {"amount": Decimal("0")},
        {"currency": "USDD"},
        {"status": TransactionStatus.PROCESSED},
    ],
)
def test_transaction_constructor_enforces_invariants(overrides: dict[str, object]) -> None:
    values: dict[str, object] = {
        "transaction_id": "txn_1",
        "source_account": "source",
        "destination_account": "destination",
        "amount": Decimal("1.00"),
        "currency": "INR",
        "status": TransactionStatus.PROCESSING,
        "created_at": datetime.now(UTC),
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        Transaction(**values)  # type: ignore[arg-type]


def test_failed_transaction_is_terminal() -> None:
    transaction = Transaction.start(
        transaction_id="txn_1",
        source_account="source",
        destination_account="destination",
        amount=Decimal("1.00"),
        currency="INR",
    )

    failed = transaction.mark_failed()

    assert failed.status is TransactionStatus.FAILED
    assert failed.mark_processed() is failed
