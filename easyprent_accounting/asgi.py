"""FastAPI composition root, domain error mapping and bundled SPA delivery."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import AppConfig, load_config
from .domain import DomainError
from .integrations.gnucash import GnuCashReader
from .integrations.paperless import PaperlessAdapter, UrllibPaperlessAdapter
from .http_asset_registry import router as asset_router
from .http_dashboard import router as dashboard_router
from .http_depreciation import router as depreciation_router
from .http_expenses import router as expenses_router
from .http_linked_documents import router as linked_documents_router
from .http_metering import router as metering_router
from .http_models import ErrorDetail, ErrorResponse
from .http_settlement_documents import router as settlement_documents_router
from .http_settings import router as settings_router
from .http_settlements import router as settlements_router
from .http_tenancy import router as tenancy_router
from .runtime_schema import prepare_database


def _generate_unique_id(route: APIRoute) -> str:
    tag = route.tags[0].lower().replace(" ", "_") if route.tags else "api"
    return f"{tag}_{route.name}"


def create_asgi_app(
    config: AppConfig,
    *,
    gnucash_reader: GnuCashReader | None = None,
    paperless: PaperlessAdapter | None = None,
    validate_schema_on_startup: bool = False,
) -> FastAPI:
    """Build a configured FastAPI instance from an injected configuration."""

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if validate_schema_on_startup:
            prepare_database(config.db_path)
        yield

    app = FastAPI(
        title="EasyPrent Accounting",
        version="0.1.0",
        generate_unique_id_function=_generate_unique_id,
        responses={422: {"model": ErrorResponse}},
        lifespan=lifespan,
    )
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
    app.include_router(settlements_router)
    app.include_router(settlement_documents_router)
    app.include_router(depreciation_router)
    app.include_router(dashboard_router)

    @app.get("/api/v1/health", tags=["Health"])
    def health() -> dict:
        return {
            "status": "ok",
            "reachable": True,
            "checked_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        }

    static_dist = Path(__file__).with_name("static_dist")
    assets = static_dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.exception_handler(StarletteHTTPException)
    async def spa_fallback_handler(
        request: Request, exc: StarletteHTTPException
    ) -> FileResponse | JSONResponse:
        path = request.url.path
        if (
            exc.status_code == 404
            and request.method in {"GET", "HEAD"}
            and not path.startswith(("/api/", "/assets/", "/static/"))
        ):
            index = static_dist / "index.html"
            if index.is_file():
                return FileResponse(index)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    return app


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=ErrorDetail(code=exc.code, reason=exc.reason)
            ).model_dump(mode="json"),
        )

    @app.exception_handler(ValueError)
    def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=ErrorDetail(code="invalid_value", reason=str(exc) or "Invalid value")
            ).model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    def request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
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


# Uvicorn and systemd use this importable ASGI entry. Database preflight runs
# during lifespan startup, before any requests are accepted.
app = create_asgi_app(load_config(dict(os.environ)), validate_schema_on_startup=True)
