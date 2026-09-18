"""Linked document metadata and download HTTP contracts."""

from __future__ import annotations

from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Path, Request, Response
from pydantic import Field

from .http_db import ReadConnection, WriteConnection
from .http_models import HttpModel
from .linked_documents import DocumentOwner, LinkedDocuments, get_paperless_status


OwnerPlural = Literal["expenses", "tenants", "leases"]
PositiveId = Annotated[int, Path(gt=0)]
OWNER_NAMES: dict[OwnerPlural, DocumentOwner] = {
    "expenses": "expense", "tenants": "tenant", "leases": "lease",
}


class DocumentWrite(HttpModel):
    filename: str | None = None
    content_type: str | None = None
    content_base64: str | None = None
    paperless_document_id: str | None = None


class DocumentBatchWrite(HttpModel):
    documents: Annotated[list[DocumentWrite], Field(min_length=1)]


class DocumentResponse(HttpModel):
    id: int
    filename: str
    content_type: str
    content_size: int
    paperless_document_id: str | None
    paperless_task_id: str | None
    paperless_reference_url: str | None
    upload_status: str
    upload_error: str | None
    created_at: str
    expense_id: int | None = None
    resource_type: DocumentOwner | None = None
    resource_id: int | None = None


class DocumentListResponse(HttpModel):
    documents: list[DocumentResponse]
    expense_id: int | None = None
    resource_type: DocumentOwner | None = None
    resource_id: int | None = None


class DocumentDeleteResponse(HttpModel):
    document_id: int
    deleted: bool
    expense_id: int | None = None
    resource_type: DocumentOwner | None = None
    resource_id: int | None = None


class PaperlessStatusResponse(HttpModel):
    configured: bool
    reachable: bool
    message: str
    checked_at: str


router = APIRouter(tags=["Linked Documents"])


@router.get("/api/v1/paperless/status", response_model=PaperlessStatusResponse)
def paperless_status(request: Request, connection: ReadConnection) -> dict:
    return get_paperless_status(connection, request.app.state.paperless)


@router.get("/api/v1/{owner_type}/{owner_id}/documents", response_model=DocumentListResponse)
def list_documents(owner_type: OwnerPlural, owner_id: PositiveId, request: Request, connection: ReadConnection) -> dict:
    return LinkedDocuments(connection, request.app.state.paperless).list(OWNER_NAMES[owner_type], owner_id)


@router.post("/api/v1/{owner_type}/{owner_id}/documents", status_code=201, response_model=DocumentListResponse)
def add_documents(
    owner_type: OwnerPlural, owner_id: PositiveId, payload: DocumentBatchWrite,
    request: Request, connection: WriteConnection,
) -> dict:
    return LinkedDocuments(connection, request.app.state.paperless).add(
        OWNER_NAMES[owner_type], owner_id, payload.model_dump(exclude_none=True)
    )


@router.delete("/api/v1/{owner_type}/{owner_id}/documents/{document_id}", response_model=DocumentDeleteResponse)
def delete_document(
    owner_type: OwnerPlural, owner_id: PositiveId, document_id: PositiveId,
    request: Request, connection: WriteConnection,
) -> dict:
    return LinkedDocuments(connection, request.app.state.paperless).delete(
        OWNER_NAMES[owner_type], owner_id, document_id
    )


@router.get(
    "/api/v1/{owner_type}/{owner_id}/documents/{document_id}/download",
    response_class=Response,
)
def download_document(
    owner_type: OwnerPlural, owner_id: PositiveId, document_id: PositiveId,
    request: Request, connection: ReadConnection,
) -> Response:
    document = LinkedDocuments(connection, request.app.state.paperless).download(
        OWNER_NAMES[owner_type], owner_id, document_id
    )
    filename = quote(document["filename"], safe="")
    return Response(
        content=document["content_blob"],
        media_type=document["content_type"],
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
