from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from confluencr.domain.repositories import TransactionRepository
from confluencr.domain.transaction import Transaction, TransactionStatus
from confluencr.infrastructure.persistence.models import TransactionModel


class SqlAlchemyTransactionRepository(TransactionRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, transaction_id: str) -> Transaction | None:
        model = self._session.get(TransactionModel, transaction_id)
        return self._to_domain(model) if model else None

    def list_processing(self) -> list[str]:
        statement = select(TransactionModel.transaction_id).where(
            TransactionModel.status == TransactionStatus.PROCESSING
        )
        return list(self._session.scalars(statement))

    def create_if_absent(self, transaction: Transaction) -> bool:
        model = TransactionModel(
            transaction_id=transaction.transaction_id,
            source_account=transaction.source_account,
            destination_account=transaction.destination_account,
            amount=transaction.amount,
            currency=transaction.currency,
            status=transaction.status,
            created_at=transaction.created_at,
            processed_at=transaction.processed_at,
        )
        self._session.add(model)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            return False
        return True

    def mark_processed(self, transaction_id: str) -> Transaction | None:
        model = self._session.get(TransactionModel, transaction_id)
        if model is None:
            return None
        domain_transaction = self._to_domain(model)
        domain_transaction.mark_processed()
        model.status = domain_transaction.status
        model.processed_at = domain_transaction.processed_at
        self._session.commit()
        return domain_transaction

    def close(self) -> None:
        self._session.close()

    @staticmethod
    def _to_domain(model: TransactionModel) -> Transaction:
        return Transaction(
            transaction_id=model.transaction_id,
            source_account=model.source_account,
            destination_account=model.destination_account,
            amount=model.amount,
            currency=model.currency,
            status=model.status,
            created_at=model.created_at,
            processed_at=model.processed_at,
        )

