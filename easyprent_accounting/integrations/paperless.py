"""Paperless HTTP adapter used by linked documents."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from socket import timeout as socket_timeout
from typing import Any, Callable, Protocol


class PaperlessAdapter(Protocol):
    def check_reachability(self, base_url: str, token: str) -> tuple[bool, str]: ...

    def upload_document(
        self, base_url: str, token: str, filename: str, content_type: str, content_blob: bytes
    ) -> dict: ...

    def download_document(
        self, base_url: str, token: str, paperless_document_id: str, fallback_filename: str
    ) -> dict: ...


def _paperless_is_configured(base_url: str, token: str) -> bool:
    return base_url != "" and token != ""


def _check_paperless_reachability(
    base_url: str, token: str, opener: Callable[..., Any]
) -> tuple[bool, str]:
    if base_url == "" or token == "":
        return False, "Paperless ist nicht konfiguriert."

    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/document_types/?page_size=1",
        headers={
            "Accept": "application/json",
            "Authorization": f"Token {token}",
        },
        method="GET",
    )
    try:
        with opener(request, timeout=5) as response:
            if 200 <= response.status < 400:
                return True, "Paperless Server erreichbar."
            return False, f"Paperless antwortet mit HTTP {response.status}."
    except urllib.error.HTTPError as error:
        return False, f"Paperless antwortet mit HTTP {error.code}."
    except (urllib.error.URLError, TimeoutError, socket_timeout) as error:
        return False, f"Paperless nicht erreichbar: {error}."


def _extract_paperless_identifiers(payload: object) -> tuple[str | None, str | None]:
    document_id: str | None = None
    task_id: str | None = None

    if isinstance(payload, int):
        document_id = str(payload)
    elif isinstance(payload, str):
        trimmed = payload.strip()
        if trimmed:
            if trimmed.isdigit():
                document_id = trimmed
            else:
                task_id = trimmed
    elif isinstance(payload, dict):
        for key in ("related_document", "document_id", "paperless_id"):
            candidate = payload.get(key)
            if isinstance(candidate, int):
                document_id = str(candidate)
                break
            if isinstance(candidate, str) and candidate.strip().isdigit():
                document_id = candidate.strip()
                break
        for key in ("task_id", "task", "uuid"):
            candidate = payload.get(key)
            if isinstance(candidate, str) and candidate.strip():
                task_id = candidate.strip()
                break
        if document_id is None:
            candidate_id = payload.get("id")
            if isinstance(candidate_id, int):
                document_id = str(candidate_id)
            elif isinstance(candidate_id, str) and candidate_id.strip().isdigit():
                document_id = candidate_id.strip()
        result_payload = payload.get("result")
        if document_id is None and isinstance(result_payload, dict):
            result_candidate = result_payload.get("document_id") or result_payload.get("related_document")
            if isinstance(result_candidate, int):
                document_id = str(result_candidate)
            elif isinstance(result_candidate, str) and result_candidate.strip().isdigit():
                document_id = result_candidate.strip()
    return document_id, task_id


def paperless_document_url(base_url: str, document_id: str | None) -> str | None:
    if not document_id:
        return None
    return base_url.rstrip("/") + "/documents/" + document_id + "/details/"


def _filename_from_content_disposition(content_disposition: str | None) -> str | None:
    if not content_disposition:
        return None
    for segment in str(content_disposition).split(";")[1:]:
        normalized_segment = segment.strip()
        if normalized_segment.lower().startswith("filename="):
            filename = normalized_segment.split("=", 1)[1].strip().strip('"')
            return filename or None
    return None


def _upload_document_to_paperless(
    base_url: str,
    token: str,
    filename: str,
    content_type: str,
    content_blob: bytes,
    opener: Callable[..., Any],
) -> dict:
    if not _paperless_is_configured(base_url, token):
        raise ValueError("Paperless configuration is required for file uploads")

    sanitized_filename = filename.replace('"', "_")
    boundary = "----easyprent-" + uuid.uuid4().hex
    multipart_body = [
        f"--{boundary}\r\n".encode("utf-8"),
        f'Content-Disposition: form-data; name="document"; filename="{sanitized_filename}"\r\n'.encode(
            "utf-8"
        ),
        f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
        content_blob,
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/documents/post_document/",
        data=b"".join(multipart_body),
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with opener(request, timeout=15) as response:
            raw_body = response.read().decode("utf-8").strip()
            if raw_body == "":
                parsed_payload: object = {}
            else:
                try:
                    parsed_payload = json.loads(raw_body)
                except ValueError:
                    parsed_payload = raw_body
        document_id, task_id = _extract_paperless_identifiers(parsed_payload)
        return {
            "upload_status": "paperless_uploaded" if document_id else "paperless_queued",
            "paperless_document_id": document_id,
            "paperless_task_id": task_id,
            "paperless_reference_url": paperless_document_url(base_url, document_id),
            "upload_error": None,
        }
    except Exception as error:  # pragma: no cover - network behavior depends on runtime
        return {
            "upload_status": "paperless_error",
            "paperless_document_id": None,
            "paperless_task_id": None,
            "paperless_reference_url": None,
            "upload_error": str(error),
        }


def _download_document_from_paperless(
    base_url: str,
    token: str,
    paperless_document_id: str,
    fallback_filename: str,
    opener: Callable[..., Any],
) -> dict:
    if base_url == "" or token == "":
        raise ValueError("paperless settings are not configured")

    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/documents/" + paperless_document_id + "/download/",
        headers={
            "Accept": "*/*",
            "Authorization": f"Token {token}",
        },
        method="GET",
    )
    try:
        with opener(request, timeout=15) as response:
            content_blob = response.read()
            content_type = str(
                response.headers.get("Content-Type") or "application/octet-stream"
            )
            filename = _filename_from_content_disposition(
                response.headers.get("Content-Disposition")
            ) or fallback_filename
    except urllib.error.HTTPError as error:
        raise ValueError(f"paperless document fetch failed with HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, socket_timeout) as error:
        raise ValueError(f"paperless document fetch failed: {error}") from error

    if len(content_blob) == 0:
        raise ValueError("paperless document is empty")

    return {
        "filename": filename,
        "content_type": content_type,
        "content_blob": content_blob,
    }


class UrllibPaperlessAdapter:
    def __init__(self, opener: Callable[..., Any] | None = None) -> None:
        self._opener = opener if opener is not None else urllib.request.urlopen

    def check_reachability(self, base_url: str, token: str) -> tuple[bool, str]:
        return _check_paperless_reachability(base_url, token, self._opener)

    def upload_document(
        self, base_url: str, token: str, filename: str, content_type: str, content_blob: bytes
    ) -> dict:
        return _upload_document_to_paperless(
            base_url, token, filename, content_type, content_blob, self._opener
        )

    def download_document(
        self, base_url: str, token: str, paperless_document_id: str, fallback_filename: str
    ) -> dict:
        return _download_document_from_paperless(
            base_url, token, paperless_document_id, fallback_filename, self._opener
        )
