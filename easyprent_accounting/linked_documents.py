"""Linked document operations and Paperless orchestration."""

from __future__ import annotations

import base64
import binascii
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from .integrations.paperless import PaperlessAdapter, paperless_document_url

DocumentOwner = Literal["expense", "tenant", "lease"]


def _latest_paperless_credentials(connection: sqlite3.Connection) -> tuple[str, str]:
    row = connection.execute(
        """
        SELECT base_url, api_token
        FROM paperless_settings
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return "", ""
    return str(row["base_url"] or ""), str(row["api_token"] or "")


def get_paperless_status(
    connection: sqlite3.Connection, paperless: PaperlessAdapter
) -> dict:
    base_url, token = _latest_paperless_credentials(connection)
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    if base_url == "" or token == "":
        return {
            "configured": False,
            "reachable": False,
            "message": "Paperless ist nicht konfiguriert.",
            "checked_at": timestamp,
        }

    reachable, message = paperless.check_reachability(base_url, token)
    return {
        "configured": True,
        "reachable": reachable,
        "message": message,
        "checked_at": timestamp,
    }


MAX_DOCUMENT_SIZE = 15 * 1024 * 1024


@dataclass(frozen=True)
class _DocumentOwner:
    name: DocumentOwner
    table: str
    owner_table: str
    owner_field: str


_OWNERS: dict[DocumentOwner, _DocumentOwner] = {
    "expense": _DocumentOwner("expense", "expense_documents", "expense_items", "expense_id"),
    "tenant": _DocumentOwner("tenant", "tenant_documents", "tenants", "tenant_id"),
    "lease": _DocumentOwner("lease", "lease_documents", "leases", "lease_id"),
}


def _owner(resource_type: DocumentOwner) -> _DocumentOwner:
    try:
        return _OWNERS[resource_type]
    except KeyError as error:
        raise ValueError(f"unsupported document resource: {resource_type}") from error


def _require_owner(
    connection: sqlite3.Connection,
    owner: _DocumentOwner,
    resource_id: int,
    *,
    editable: bool = False,
) -> None:
    columns = "id, is_archived" if owner.name == "expense" else "id"
    row = connection.execute(
        f"SELECT {columns} FROM {owner.owner_table} WHERE id = ?",
        (resource_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"{owner.name} not found")
    if editable and owner.name == "expense" and int(row["is_archived"] or 0):
        raise ValueError("archived expenses cannot be edited")


def _normalize_paperless_document_id(raw_value: object, field_name: str) -> str:
    normalized = str(raw_value or "").strip()
    if normalized == "":
        raise ValueError(f"{field_name} is required")
    if not normalized.isdigit():
        raise ValueError(f"{field_name} must be an integer string")
    return normalized


def _normalize_linked_documents_payload(payload: dict, base_url: str) -> list[dict]:
    documents = payload.get("documents")
    if not isinstance(documents, list) or len(documents) == 0:
        raise ValueError("documents must be a non-empty array")
    normalized_documents: list[dict] = []
    for index, document_payload in enumerate(documents):
        if not isinstance(document_payload, dict):
            raise ValueError(f"documents[{index}] must be an object")
        paperless_document_id = str(document_payload.get("paperless_document_id") or "").strip()
        if paperless_document_id != "":
            if base_url == "":
                raise ValueError("paperless_document_id requires configured Paperless settings")
            normalized_paperless_document_id = _normalize_paperless_document_id(
                paperless_document_id,
                f"documents[{index}].paperless_document_id",
            )
            filename = str(document_payload.get("filename") or "").strip()
            normalized_documents.append(
                {
                    "filename": filename or f"paperless-document-{normalized_paperless_document_id}",
                    "content_type": str(
                        document_payload.get("content_type") or "application/octet-stream"
                    ).strip(),
                    "content_blob": b"",
                    "skip_paperless_upload": True,
                    "paperless_document_id": normalized_paperless_document_id,
                    "paperless_task_id": None,
                    "paperless_reference_url": paperless_document_url(
                        base_url,
                        normalized_paperless_document_id,
                    ),
                    "upload_status": "paperless_linked",
                    "upload_error": None,
                }
            )
            continue
        filename = str(document_payload.get("filename") or "").strip()
        if filename == "":
            raise ValueError(f"documents[{index}].filename is required")
        if base_url == "":
            raise ValueError("Paperless configuration is required for file uploads")
        content_type = str(document_payload.get("content_type") or "application/octet-stream").strip()
        content_base64 = str(document_payload.get("content_base64") or "").strip()
        if content_base64 == "":
            raise ValueError(f"documents[{index}].content_base64 is required")
        try:
            content_blob = base64.b64decode(content_base64, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError(f"documents[{index}].content_base64 must be valid base64") from error
        if len(content_blob) == 0:
            raise ValueError(f"documents[{index}] is empty")
        if len(content_blob) > MAX_DOCUMENT_SIZE:
            raise ValueError(
                f"documents[{index}] exceeds max size of {MAX_DOCUMENT_SIZE} bytes"
            )
        normalized_documents.append(
            {
                "filename": filename,
                "content_type": content_type,
                "content_blob": content_blob,
                "skip_paperless_upload": False,
            }
        )
    return normalized_documents


def _document_rows(
    connection: sqlite3.Connection,
    owner: _DocumentOwner,
    resource_id: int,
    document_ids: list[int] | None = None,
) -> list[dict]:
    where = f"{owner.owner_field} = ?"
    parameters: list[int] = [resource_id]
    if document_ids is not None:
        if not document_ids:
            return []
        where += " AND id IN (" + ",".join("?" for _ in document_ids) + ")"
        parameters.extend(document_ids)
    rows = connection.execute(
        f"""
        SELECT id, {owner.owner_field} AS owner_id, filename, content_type,
               content_size, paperless_document_id, paperless_task_id,
               paperless_reference_url, upload_status, upload_error, created_at
        FROM {owner.table}
        WHERE {where}
        ORDER BY id
        """,
        parameters,
    ).fetchall()
    documents = []
    for row in rows:
        document = {
            "id": int(row["id"]),
            "filename": str(row["filename"]),
            "content_type": str(row["content_type"]),
            "content_size": int(row["content_size"]),
            "paperless_document_id": row["paperless_document_id"],
            "paperless_task_id": row["paperless_task_id"],
            "paperless_reference_url": row["paperless_reference_url"],
            "upload_status": str(row["upload_status"]),
            "upload_error": row["upload_error"],
            "created_at": row["created_at"],
        }
        if owner.name == "expense":
            document["expense_id"] = int(row["owner_id"])
        else:
            document["resource_type"] = owner.name
            document["resource_id"] = int(row["owner_id"])
        documents.append(document)
    return documents


def _list_response(
    connection: sqlite3.Connection,
    owner: _DocumentOwner,
    resource_id: int,
    document_ids: list[int] | None = None,
) -> dict:
    result = {"documents": _document_rows(connection, owner, resource_id, document_ids)}
    if owner.name == "expense":
        result["expense_id"] = resource_id
    else:
        result["resource_type"] = owner.name
        result["resource_id"] = resource_id
    return result


class LinkedDocuments:
    """Manage local links to expense, tenant, and lease documents."""

    def __init__(self, connection: sqlite3.Connection, paperless: PaperlessAdapter) -> None:
        self.connection = connection
        self.paperless = paperless

    def list(self, resource_type: DocumentOwner, resource_id: int) -> dict:
        owner = _owner(resource_type)
        _require_owner(self.connection, owner, resource_id)
        return _list_response(self.connection, owner, resource_id)

    def add(self, resource_type: DocumentOwner, resource_id: int, payload: dict) -> dict:
        owner = _owner(resource_type)
        _require_owner(self.connection, owner, resource_id, editable=True)
        base_url, token = _latest_paperless_credentials(self.connection)
        normalized = _normalize_linked_documents_payload(payload, base_url)
        created_ids = []
        timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()

        for document in normalized:
            if document["skip_paperless_upload"]:
                paperless_result = document
            else:
                paperless_result = self.paperless.upload_document(
                    base_url,
                    token,
                    document["filename"],
                    document["content_type"],
                    document["content_blob"],
                )
                if (
                    paperless_result["paperless_document_id"] in (None, "")
                    and paperless_result["paperless_task_id"] in (None, "")
                ):
                    raise ValueError(
                        "document upload to Paperless failed: "
                        + str(paperless_result["upload_error"] or "unknown error")
                    )
            cursor = self.connection.execute(
                f"""
                INSERT INTO {owner.table} (
                    {owner.owner_field}, filename, content_type, content_size,
                    content_blob, paperless_document_id, paperless_task_id,
                    paperless_reference_url, upload_status, upload_error, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resource_id,
                    document["filename"],
                    document["content_type"],
                    len(document["content_blob"]),
                    sqlite3.Binary(b""),
                    paperless_result["paperless_document_id"],
                    paperless_result["paperless_task_id"],
                    paperless_result["paperless_reference_url"],
                    paperless_result["upload_status"],
                    paperless_result["upload_error"],
                    timestamp,
                ),
            )
            created_ids.append(int(cursor.lastrowid))
        return _list_response(self.connection, owner, resource_id, created_ids)

    def delete(self, resource_type: DocumentOwner, resource_id: int, document_id: int) -> dict:
        owner = _owner(resource_type)
        _require_owner(self.connection, owner, resource_id, editable=True)
        row = self.connection.execute(
            f"SELECT id FROM {owner.table} "
            f"WHERE id = ? AND {owner.owner_field} = ?",
            (document_id, resource_id),
        ).fetchone()
        if row is None:
            raise ValueError(f"{owner.name} document not found")
        self.connection.execute(
            f"DELETE FROM {owner.table} "
            f"WHERE id = ? AND {owner.owner_field} = ?",
            (document_id, resource_id),
        )
        result = {"document_id": document_id, "deleted": True}
        if owner.name == "expense":
            result["expense_id"] = resource_id
        else:
            result["resource_type"] = owner.name
            result["resource_id"] = resource_id
        return result

    def download(self, resource_type: DocumentOwner, resource_id: int, document_id: int) -> dict:
        owner = _owner(resource_type)
        if owner.name != "expense":
            _require_owner(self.connection, owner, resource_id)
        row = self.connection.execute(
            f"SELECT filename, content_type, content_blob, paperless_document_id "
            f"FROM {owner.table} WHERE id = ? AND {owner.owner_field} = ?",
            (document_id, resource_id),
        ).fetchone()
        if row is None:
            raise ValueError(f"{owner.name} document not found")
        content_blob = bytes(row["content_blob"])
        if content_blob:
            return {
                "filename": str(row["filename"]),
                "content_type": str(row["content_type"] or "application/octet-stream"),
                "content_blob": content_blob,
            }
        if row["paperless_document_id"] not in (None, ""):
            base_url, token = _latest_paperless_credentials(self.connection)
            return self.paperless.download_document(
                base_url,
                token,
                str(row["paperless_document_id"]),
                str(row["filename"]),
            )
        raise ValueError(f"{owner.name} document has no downloadable content")
