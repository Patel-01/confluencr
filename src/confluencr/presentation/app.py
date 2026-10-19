from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from confluencr.application.services import TransactionProcessingService
from confluencr.core.config import Settings, get_settings
from confluencr.core.database import Base, create_database_engine, create_session_factory
from confluencr.infrastructure.persistence.repositories import SqlAlchemyTransactionRepository
from confluencr.infrastructure.workers.in_process import InProcessTransactionProcessor
from confluencr.presentation.routes import router


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    engine = create_database_engine(runtime_settings.database_url)
    session_factory = create_session_factory(engine)
    Base.metadata.create_all(engine)

    def repository_factory() -> SqlAlchemyTransactionRepository:
        return SqlAlchemyTransactionRepository(session_factory())

    processing_service = TransactionProcessingService(
        repository_factory=repository_factory,
        delay_seconds=runtime_settings.processing_delay_seconds,
    )
    processor = InProcessTransactionProcessor(
        processing_service=processing_service,
        max_workers=runtime_settings.worker_max_workers,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        processor.shutdown()
        engine.dispose()

    app = FastAPI(title=runtime_settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in runtime_settings.cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.session_factory = session_factory
    app.state.transaction_processor = processor
    app.state.engine = engine
    app.include_router(router)

    frontend_dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app

