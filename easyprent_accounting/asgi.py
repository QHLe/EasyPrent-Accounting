"""ASGI application factory with injectable config and domain error mapping."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from .config import AppConfig
from .domain import DomainError
from .integrations.gnucash import GnuCashReader
from .integrations.paperless import PaperlessAdapter, UrllibPaperlessAdapter
from .http_asset_registry import router as asset_router
from .http_expenses import router as expenses_router
from .http_linked_documents import router as linked_documents_router
from .http_metering import router as metering_router
from .http_models import ErrorDetail, ErrorResponse
from .http_settings import router as settings_router
from .http_tenancy import router as tenancy_router
from .services import health_status


def create_asgi_app(
    config: AppConfig,
    *,
    gnucash_reader: GnuCashReader | None = None,
    paperless: PaperlessAdapter | None = None,
) -> FastAPI:
    """Build a configured FastAPI instance.

    The factory receives an ``AppConfig`` and does **not** read
    ``os.environ`` itself.  This keeps the app injectable and testable.
    """

    app = FastAPI(title="EasyPrent Accounting", version="0.1.0")
    app.state.config = config
    app.state.gnucash_reader = gnucash_reader
    app.state.paperless = paperless or UrllibPaperlessAdapter()

    _register_error_handlers(app)
    app.include_router(expenses_router)
    app.include_router(asset_router)
    app.include_router(metering_router)
    app.include_router(tenancy_router)
    app.include_router(settings_router)
    app.include_router(linked_documents_router)

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
            content=ErrorResponse(
                error=ErrorDetail(code=exc.code, reason=exc.reason)
            ).model_dump(mode="json"),
        )

    @app.exception_handler(ValueError)
    def _value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=ErrorDetail(code="invalid_value", reason=str(exc) or "Invalid value")
            ).model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    def _request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        first_error = exc.errors()[0]
        location = ".".join(str(part) for part in first_error.get("loc", ()))
        message = str(first_error.get("msg", "Invalid request"))
        reason = f"{location}: {message}" if location else message
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=ErrorDetail(code="invalid_request", reason=reason)
            ).model_dump(mode="json"),
        )
