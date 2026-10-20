from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.engine import CursorResult
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

    def list_runnable(self, now: datetime) -> list[str]:
        statement = select(TransactionModel.transaction_id).where(
            TransactionModel.status == TransactionStatus.PROCESSING,
            or_(
                TransactionModel.next_attempt_at.is_(None),
                TransactionModel.next_attempt_at <= now,
            ),
            or_(TransactionModel.lease_until.is_(None), TransactionModel.lease_until <= now),
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
            if self._session.get(TransactionModel, transaction.transaction_id) is not None:
                return False
            raise
        return True

    def mark_processed(self, transaction_id: str, *, lease_token: str) -> Transaction | None:
        processed_at = datetime.now(UTC)
        statement = (
            update(TransactionModel)
            .where(
                TransactionModel.transaction_id == transaction_id,
                TransactionModel.status == TransactionStatus.PROCESSING,
                TransactionModel.lease_token == lease_token,
            )
            .values(
                status=TransactionStatus.PROCESSED,
                processed_at=processed_at,
                lease_until=None,
                lease_token=None,
                next_attempt_at=None,
                last_error=None,
            )
        )
        result = cast(CursorResult[Any], self._session.execute(statement))
        self._session.commit()
        if result.rowcount != 1:
            return None
        model = self._session.get(TransactionModel, transaction_id)
        return self._to_domain(model) if model else None

    def claim_for_processing(
        self, transaction_id: str, *, now: datetime, lease_until: datetime
    ) -> str | None:
        lease_token = str(uuid4())
        statement = (
            update(TransactionModel)
            .where(
                TransactionModel.transaction_id == transaction_id,
                TransactionModel.status == TransactionStatus.PROCESSING,
                or_(
                    TransactionModel.next_attempt_at.is_(None),
                    TransactionModel.next_attempt_at <= now,
                ),
                or_(TransactionModel.lease_until.is_(None), TransactionModel.lease_until <= now),
            )
            .values(
                attempt_count=TransactionModel.attempt_count + 1,
                lease_until=lease_until,
                lease_token=lease_token,
                next_attempt_at=None,
            )
        )
        result = cast(CursorResult[Any], self._session.execute(statement))
        self._session.commit()
        return lease_token if result.rowcount == 1 else None

    def record_failure(
        self,
        transaction_id: str,
        *,
        lease_token: str,
        error: str,
        max_attempts: int,
        retry_at: datetime,
    ) -> TransactionStatus | None:
        model = self._session.get(TransactionModel, transaction_id)
        if model is None or model.lease_token != lease_token:
            return None
        status = (
            TransactionStatus.FAILED
            if model.attempt_count >= max_attempts
            else TransactionStatus.PROCESSING
        )
        statement = (
            update(TransactionModel)
            .where(
                TransactionModel.transaction_id == transaction_id,
                TransactionModel.status == TransactionStatus.PROCESSING,
                TransactionModel.lease_token == lease_token,
            )
            .values(
                status=status,
                lease_until=None,
                lease_token=None,
                next_attempt_at=None if status is TransactionStatus.FAILED else retry_at,
                last_error=error[:2000],
            )
        )
        result = cast(CursorResult[Any], self._session.execute(statement))
        self._session.commit()
        return status if result.rowcount == 1 else None

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
        if client_session is not None:
            self._session.execute(
                update(ClientSessionModel)
                .where(ClientSessionModel.session_id == session_id)
                .values(
                    last_seen_at=now,
                    total_api_calls=ClientSessionModel.total_api_calls + 1,
                )
            )
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

