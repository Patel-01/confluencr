from uuid import UUID, uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from confluencr.application.session import SessionAnalyticsService


def resolve_session_id(request: Request) -> str:
    candidate = request.headers.get("X-Session-ID", "")
    try:
        return str(UUID(candidate))
    except ValueError:
        return str(uuid4())


class SessionTrackingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, analytics_service: SessionAnalyticsService) -> None:
        super().__init__(app)
        self._analytics_service = analytics_service

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        session_id = resolve_session_id(request)
        request.state.client_session_id = session_id
        response = await call_next(request)

        if request.url.path.startswith("/v1/") and not request.url.path.startswith(
            "/v1/session/"
        ):
            self._analytics_service.record_api_call_async(
                session_id=session_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
            )
        response.headers["X-Session-ID"] = session_id
        return response
