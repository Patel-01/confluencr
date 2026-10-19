from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from confluencr.domain.repositories import SessionRepository, TransactionRepository
from confluencr.domain.session import SessionActivity, SessionSummary
from confluencr.domain.transaction import Transaction, TransactionStatus
from confluencr.infrastructure.persistence.models import (
    ClientSessionModel,
    SessionActivityModel,
    TransactionModel,
)


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


class SqlAlchemySessionRepository(SessionRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def record_api_call(self, session_id: str, method: str, path: str, status_code: int) -> None:
        now = datetime.now(UTC)
        client_session = self._session.get(ClientSessionModel, session_id)
        if client_session is None:
            self._session.add(
                ClientSessionModel(
                    session_id=session_id,
                    first_seen_at=now,
                    last_seen_at=now,
                    total_api_calls=1,
                )
            )
            try:
                self._session.flush()
            except IntegrityError:
                self._session.rollback()
                client_session = self._session.get(ClientSessionModel, session_id)
                if client_session is None:
                    raise
                client_session.last_seen_at = now
                client_session.total_api_calls += 1
        else:
            client_session.last_seen_at = now
            client_session.total_api_calls += 1
        self._session.add(
            SessionActivityModel(
                session_id=session_id,
                method=method,
                path=path,
                status_code=status_code,
                created_at=now,
            )
        )
        self._session.commit()

    def get_summary(self, session_id: str) -> SessionSummary:
        client_session = self._session.get(ClientSessionModel, session_id)
        activities = list(
            self._session.scalars(
                select(SessionActivityModel)
                .where(SessionActivityModel.session_id == session_id)
                .order_by(SessionActivityModel.created_at.desc())
                .limit(10)
            )
        )
        return SessionSummary(
            session_id=session_id,
            total_api_calls=client_session.total_api_calls if client_session else 0,
            first_seen_at=client_session.first_seen_at if client_session else None,
            last_seen_at=client_session.last_seen_at if client_session else None,
            recent_activity=[
                SessionActivity(
                    method=activity.method,
                    path=activity.path,
                    status_code=activity.status_code,
                    created_at=activity.created_at,
                )
                for activity in activities
            ],
        )

    def close(self) -> None:
        self._session.close()

