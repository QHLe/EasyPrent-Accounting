"""Settlement PDF and ODS download routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Path, Query, Request, Response

from .http_db import ReadConnection
from .settlement_documents import SettlementDocuments


PositiveQueryId = Annotated[int, Query(gt=0)]
PositivePathId = Annotated[int, Path(gt=0)]
SettlementRunId = Annotated[str, Path(min_length=1)]


router = APIRouter(tags=["Settlements"])
PDF_RESPONSE: dict[int | str, dict[str, Any]] = {
    200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}}
}
ODS_RESPONSE: dict[int | str, dict[str, Any]] = {
    200: {
        "content": {
            "application/vnd.oasis.opendocument.spreadsheet": {
                "schema": {"type": "string", "format": "binary"}
            }
        }
    }
}


def _attachment(contents: bytes, filename: str, media_type: str) -> Response:
    return Response(
        content=contents,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}"
        },
    )


def _require_one_target(property_id: int | None, unit_id: int | None) -> None:
    if (property_id is None) == (unit_id is None):
        raise ValueError("settlement requires exactly one property or standalone unit")


@router.get("/api/v1/settlements/document.pdf", response_class=Response, responses=PDF_RESPONSE)
def download_period_pdf(
    lease_id: PositiveQueryId,
    period_start: date,
    period_end: date,
    request: Request,
    connection: ReadConnection,
    property_id: PositiveQueryId | None = None,
    unit_id: PositiveQueryId | None = None,
) -> Response:
    _require_one_target(property_id, unit_id)
    contents, filename = SettlementDocuments(connection, request.app.state.config).pdf_for_period(
        property_id, lease_id, period_start.isoformat(), period_end.isoformat(), unit_id
    )
    return _attachment(contents, filename, "application/pdf")


@router.get("/api/v1/settlements/document.ods", response_class=Response, responses=ODS_RESPONSE)
def download_period_ods(
    lease_id: PositiveQueryId,
    period_start: date,
    period_end: date,
    request: Request,
    connection: ReadConnection,
    property_id: PositiveQueryId | None = None,
    unit_id: PositiveQueryId | None = None,
) -> Response:
    _require_one_target(property_id, unit_id)
    contents, filename = SettlementDocuments(connection, request.app.state.config).ods_for_period(
        property_id, lease_id, period_start.isoformat(), period_end.isoformat(), unit_id
    )
    return _attachment(contents, filename, "application/vnd.oasis.opendocument.spreadsheet")


@router.get(
    "/api/v1/settlement-runs/{settlement_id}/leases/{lease_id}/document.ods",
    response_class=Response,
    responses=ODS_RESPONSE,
)
def download_run_ods(
    settlement_id: SettlementRunId,
    lease_id: PositivePathId,
    request: Request,
    connection: ReadConnection,
) -> Response:
    contents, filename = SettlementDocuments(connection, request.app.state.config).ods_for_run(
        settlement_id, lease_id
    )
    return _attachment(contents, filename, "application/vnd.oasis.opendocument.spreadsheet")
