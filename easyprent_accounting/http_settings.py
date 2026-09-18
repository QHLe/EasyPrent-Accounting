"""Settings, GnuCash account discovery, and versioned backup HTTP contracts."""

from __future__ import annotations

from typing import Any, Annotated

from fastapi import APIRouter, Request
from pydantic import Field

from .http_db import ReadConnection, WriteConnection
from .http_models import HttpModel
from .settings import (
    export_application_data,
    get_application_settings,
    get_gnucash_settings,
    get_paperless_settings,
    import_application_data,
    list_gnucash_accounts,
    update_application_settings,
    update_gnucash_settings,
    update_paperless_settings,
)


class ApplicationSettingsWrite(HttpModel):
    show_delete_actions: bool
    sender_name: str | None = None
    sender_street: str | None = None
    sender_city: str | None = None


class ApplicationSettingsResponse(HttpModel):
    show_delete_actions: bool
    sender_name: str
    sender_street: str
    sender_city: str
    updated_at: str | None


class PaperlessSettingsWrite(HttpModel):
    base_url: str
    api_token: str | None = None


class PaperlessSettingsResponse(HttpModel):
    base_url: str
    token_present: bool
    token_masked: str | None
    updated_at: str | None


class GnuCashSettingsWrite(HttpModel):
    host: str
    port: Annotated[int, Field(strict=True, ge=1, le=65535)]
    database: str
    username: str
    password: str | None = None
    sslmode: str = "require"


class GnuCashSettingsResponse(HttpModel):
    configured: bool
    host: str
    port: int
    database: str
    username: str
    password_present: bool
    password_masked: str | None
    sslmode: str
    updated_at: str | None


class GnuCashAccountResponse(HttpModel):
    guid: str
    name: str
    full_name: str
    parent_guid: str | None


class ApplicationExportResponse(HttpModel):
    format_version: int
    exported_at: str
    table_count: int
    row_count: int
    tables: dict[str, list[dict[str, Any]]]


class ApplicationImportWrite(HttpModel):
    format_version: int
    tables: dict[str, list[dict[str, Any]]]
    exported_at: str | None = None
    table_count: int | None = None
    row_count: int | None = None


class ApplicationImportResponse(HttpModel):
    format_version: int
    imported_at: str
    table_count: int
    row_count: int
    skipped_legacy_gnucash_payments: int
    migrated_legacy_gnucash_accounts: int


router = APIRouter(prefix="/api/v1/settings", tags=["Settings and Backup"])


@router.get("/application", response_model=ApplicationSettingsResponse)
def read_application_settings(connection: ReadConnection) -> dict:
    return get_application_settings(connection)


@router.put("/application", response_model=ApplicationSettingsResponse)
def write_application_settings(payload: ApplicationSettingsWrite, connection: WriteConnection) -> dict:
    return update_application_settings(connection, payload.model_dump(exclude_none=True))


@router.get("/paperless", response_model=PaperlessSettingsResponse)
def read_paperless_settings(connection: ReadConnection) -> dict:
    return get_paperless_settings(connection)


@router.put("/paperless", response_model=PaperlessSettingsResponse)
def write_paperless_settings(payload: PaperlessSettingsWrite, connection: WriteConnection) -> dict:
    return update_paperless_settings(connection, payload.model_dump(exclude_none=True))


@router.get("/gnucash", response_model=GnuCashSettingsResponse)
def read_gnucash_settings(connection: ReadConnection) -> dict:
    return get_gnucash_settings(connection)


@router.put("/gnucash", response_model=GnuCashSettingsResponse)
def write_gnucash_settings(payload: GnuCashSettingsWrite, connection: WriteConnection) -> dict:
    return update_gnucash_settings(connection, payload.model_dump(exclude_none=True))


@router.get("/gnucash/accounts", response_model=list[GnuCashAccountResponse])
def read_gnucash_accounts(request: Request, connection: ReadConnection) -> list[dict]:
    return list_gnucash_accounts(connection, request.app.state.gnucash_reader)


@router.get("/export", response_model=ApplicationExportResponse)
def export_application(connection: ReadConnection) -> ApplicationExportResponse:
    return ApplicationExportResponse.model_validate(export_application_data(connection))


@router.post("/import", response_model=ApplicationImportResponse)
def import_application(payload: ApplicationImportWrite, connection: WriteConnection) -> dict:
    return import_application_data(connection, payload.model_dump(exclude_none=True))
