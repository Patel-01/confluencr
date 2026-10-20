from collections.abc import Generator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from confluencr.application.services import TransactionApplicationService
from confluencr.application.session import SessionAnalyticsService
from confluencr.infrastructure.persistence.repositories import SqlAlchemyTransactionRepository


def get_session(request: Request) -> Generator[Session, None, None]:
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_transaction_service(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> TransactionApplicationService:
    processor = request.app.state.transaction_processor
    repository = SqlAlchemyTransactionRepository(session)
    return TransactionApplicationService(repository=repository, processor=processor)


def get_session_analytics_service(request: Request) -> SessionAnalyticsService:
    return cast(SessionAnalyticsService, request.app.state.session_analytics_service)

