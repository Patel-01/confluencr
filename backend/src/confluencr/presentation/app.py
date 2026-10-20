from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from confluencr.application.services import TransactionProcessingService
from confluencr.application.session import SessionAnalyticsService
from confluencr.core.config import Settings, get_settings
from confluencr.core.database import create_database_engine, create_session_factory
from confluencr.infrastructure.persistence.repositories import (
    SqlAlchemySessionRepository,
    SqlAlchemyTransactionRepository,
)
from confluencr.infrastructure.workers.in_process import InProcessTransactionProcessor
from confluencr.presentation.frontend_assets import frontend_dist_path
from confluencr.presentation.middleware import SessionTrackingMiddleware
from confluencr.presentation.routes import router


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    engine = create_database_engine(runtime_settings.database_url)
    session_factory = create_session_factory(engine)
    def repository_factory() -> SqlAlchemyTransactionRepository:
        return SqlAlchemyTransactionRepository(session_factory())

    processing_service = TransactionProcessingService(
        repository_factory=repository_factory,
        delay_seconds=runtime_settings.processing_delay_seconds,
        lease_seconds=runtime_settings.worker_lease_seconds,
        max_attempts=runtime_settings.worker_max_attempts,
    )
    processor = InProcessTransactionProcessor(
        processing_service=processing_service,
        repository_factory=repository_factory,
        max_workers=runtime_settings.worker_max_workers,
    )
    session_analytics_service = SessionAnalyticsService(
        repository_factory=lambda: SqlAlchemySessionRepository(session_factory()),
        max_workers=runtime_settings.worker_max_workers,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        processor.start()
        yield
        processor.shutdown()
        session_analytics_service.shutdown()
        engine.dispose()

    app = FastAPI(title=runtime_settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in runtime_settings.cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Session-ID"],
    )
    app.add_middleware(
        SessionTrackingMiddleware,
        analytics_service=session_analytics_service,
    )
    app.state.session_factory = session_factory
    app.state.transaction_processor = processor
    app.state.session_analytics_service = session_analytics_service
    app.state.engine = engine
    app.include_router(router)

    frontend_dist = frontend_dist_path()
    if frontend_dist.is_dir():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    return app

