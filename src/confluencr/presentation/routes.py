from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from confluencr.application.services import TransactionApplicationService
from confluencr.domain.exceptions import TransactionNotFoundError
from confluencr.presentation.dependencies import get_transaction_service
from confluencr.presentation.schemas import (
    HealthResponse,
    TransactionResponse,
    TransactionWebhookRequest,
    WebhookAcceptedResponse,
)

router = APIRouter()


@router.get("/", response_model=None)
def root(request: Request) -> HealthResponse | FileResponse:
    """Keep the assessment health contract while serving the browser UI."""
    frontend_index = Path.cwd() / "frontend" / "dist" / "index.html"
    accepts_html = "text/html" in request.headers.get("accept", "")
    if accepts_html and frontend_index.is_file():
        return FileResponse(frontend_index, media_type="text/html")
    return HealthResponse(status="HEALTHY", current_time=datetime.now(UTC))


@router.get("/healthz", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="HEALTHY", current_time=datetime.now(UTC))


@router.post(
    "/v1/webhooks/transactions",
    response_model=WebhookAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def receive_transaction_webhook(
    payload: TransactionWebhookRequest,
    service: Annotated[TransactionApplicationService, Depends(get_transaction_service)],
) -> WebhookAcceptedResponse:
    service.receive_webhook(payload.to_domain())
    return WebhookAcceptedResponse(transaction_id=payload.transaction_id.strip())


@router.get(
    "/v1/transactions/{transaction_id}",
    response_model=list[TransactionResponse],
)
def get_transaction(
    transaction_id: str,
    service: Annotated[TransactionApplicationService, Depends(get_transaction_service)],
) -> list[TransactionResponse]:
    try:
        transaction = service.get_transaction(transaction_id)
    except TransactionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [TransactionResponse.from_domain(transaction)]

