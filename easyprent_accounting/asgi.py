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
from .services import health_status


from fastapi.routing import APIRoute

def _generate_unique_id(route: APIRoute) -> str:
    tag = route.tags[0].lower().replace(" ", "_") if route.tags else "api"
    return f"{tag}_{route.name}"

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

    app = FastAPI(
        title="EasyPrent Accounting",
        version="0.1.0",
        generate_unique_id_function=_generate_unique_id,
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

    # ── Health ──────────────────────────────────────────────────────
    @app.get("/api/v1/health", tags=["Health"])
    def health() -> dict:
        return health_status()

    # ── Static files & SPA fallback ────────────────────────────────
    import os
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from starlette.exceptions import HTTPException as StarletteHTTPException

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    static_dist_dir = os.path.join(os.path.dirname(__file__), "static_dist")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    if os.path.isdir(os.path.join(static_dist_dir, "assets")):
        app.mount("/assets", StaticFiles(directory=os.path.join(static_dist_dir, "assets")), name="assets")

    @app.exception_handler(StarletteHTTPException)
    async def spa_fallback_handler(request: Request, exc: StarletteHTTPException) -> FileResponse | JSONResponse:
        if exc.status_code == 404 and not request.url.path.startswith("/api/"):
            if request.url.path.startswith("/static/") or request.url.path.startswith("/assets/"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            index_path = os.path.join(static_dist_dir, "index.html")
            if os.path.isfile(index_path):
                return FileResponse(index_path)
            # Fallback to legacy index for tests if dist not built yet
            return FileResponse(os.path.join(static_dir, "index.html"))
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    from fastapi.openapi.utils import get_openapi
    
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            description=app.description,
            routes=app.routes,
        )
        
        # Replace HTTPValidationError with our ErrorResponse schema
        if "components" not in openapi_schema:
            openapi_schema["components"] = {}
        if "schemas" not in openapi_schema["components"]:
            openapi_schema["components"]["schemas"] = {}
        
        schemas = openapi_schema["components"]["schemas"]
        if "HTTPValidationError" in schemas:
            del schemas["HTTPValidationError"]
        if "ValidationError" in schemas:
            del schemas["ValidationError"]
            
        from .http_models import ErrorResponse
        error_response_schema = ErrorResponse.model_json_schema(ref_template="#/components/schemas/{model}")
        if "$defs" in error_response_schema:
            for def_name, def_schema in error_response_schema.pop("$defs").items():
                schemas[def_name] = def_schema
        schemas["ErrorResponse"] = error_response_schema
        
        for path in openapi_schema.get("paths", {}).values():
            for operation in path.values():
                if "responses" in operation and "422" in operation["responses"]:
                    operation["responses"]["422"] = {
                        "description": "Validation Error",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                    }
        app.openapi_schema = openapi_schema
        return app.openapi_schema
        
    app.openapi = custom_openapi

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
