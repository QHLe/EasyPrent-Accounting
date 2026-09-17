"""ASGI application factory with injectable config and domain error mapping."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from .config import AppConfig
from .domain import DomainError
from .services import health_status


def create_asgi_app(config: AppConfig) -> FastAPI:
    """Build a configured FastAPI instance.

    The factory receives an ``AppConfig`` and does **not** read
    ``os.environ`` itself.  This keeps the app injectable and testable.
    """

    app = FastAPI(title="EasyPrent Accounting", version="0.1.0")
    app.state.config = config

    _register_error_handlers(app)

    # ── Health ──────────────────────────────────────────────────────
    @app.get("/api/v1/health")
    def health() -> dict:
        return health_status()

    return app


# ── Error handlers ─────────────────────────────────────────────────


def _register_error_handlers(app: FastAPI) -> None:
    """Map domain exceptions to a uniform HTTP error envelope."""

    @app.exception_handler(DomainError)
    def _domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": exc.code,
                    "reason": exc.reason,
                },
            },
        )
