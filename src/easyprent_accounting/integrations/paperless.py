from __future__ import annotations
import asyncio
from datetime import date
from typing import Optional, Sequence
import httpx

from app.serialization import parse_date_value


class PaperlessService:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._client = httpx.AsyncClient(base_url=self.base_url, headers={
            "Authorization": f"Token {self.token}",
        }, follow_redirects=True)

    async def close(self):
        await self._client.aclose()

    async def test_connection(self) -> None:
        resp = await self._client.get("/api/document_types/", params={"page_size": 1})
        if resp.status_code >= 400:
            txt = resp.text[:300]
            raise RuntimeError(f"Paperless connection failed: {resp.status_code} {txt}")

    async def list_document_types(self) -> list[dict]:
        """List all document types from Paperless."""
        resp = await self._client.get("/api/document_types/")
        resp.raise_for_status()
        return resp.json().get("results", [])

    async def list_correspondents(self) -> list[dict]:
        """List all correspondents from Paperless."""
        resp = await self._client.get("/api/correspondents/")
        resp.raise_for_status()
        return resp.json().get("results", [])

    async def list_tags(self) -> list[dict]:
        """List all tags from Paperless."""
        resp = await self._client.get("/api/tags/")
        resp.raise_for_status()
        return resp.json().get("results", [])

    async def create_document_type(self, name: str, match: Optional[str] = None, matching_algorithm: int = 0) -> dict:
        """Create a new document type in Paperless."""
        data = {"name": name, "match": match or "", "matching_algorithm": matching_algorithm}
        resp = await self._client.post("/api/document_types/", json=data)
        if resp.status_code >= 400:
            txt = resp.text[:500]
            raise RuntimeError(f"Failed to create document type: {resp.status_code} {txt}")
        return resp.json()

    async def create_correspondent(self, name: str, match: Optional[str] = None, matching_algorithm: int = 0) -> dict:
        """Create a new correspondent in Paperless."""
        data = {"name": name, "match": match or "", "matching_algorithm": matching_algorithm}
        resp = await self._client.post("/api/correspondents/", json=data)
        if resp.status_code >= 400:
            txt = resp.text[:500]
            raise RuntimeError(f"Failed to create correspondent: {resp.status_code} {txt}")
        return resp.json()

    async def create_tag(self, name: str, color: Optional[str] = None, match: Optional[str] = None, matching_algorithm: int = 0) -> dict:
        """Create a new tag in Paperless."""
        data = {"name": name, "color": color or "#a6cee3", "match": match or "", "matching_algorithm": matching_algorithm}
        resp = await self._client.post("/api/tags/", json=data)
        if resp.status_code >= 400:
            txt = resp.text[:500]
            raise RuntimeError(f"Failed to create tag: {resp.status_code} {txt}")
        return resp.json()

    async def _resolve_id(self, name: str, endpoint: str) -> Optional[int]:
        """Resolve a name to an ID by fetching from Paperless API."""
        resp = await self._client.get(endpoint)
        if resp.status_code >= 400:
            return None
        results = resp.json().get("results", [])
        for item in results:
            if item.get("name", "").lower() == name.lower():
                return item.get("id")
        return None

    async def upload_document(
        self,
        content: bytes,
        filename: str,
        document_type: Optional[str] = None,
        correspondent: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
    ) -> dict:
        # Paperless-ngx uses /api/documents/post_document/ for uploads
        files = {"document": (filename, content, "application/octet-stream")}
        data = {}
        
        # Resolve document_type: if not numeric, try to find by name
        if document_type:
            if document_type.isdigit():
                data["document_type"] = document_type
            else:
                doc_type_id = await self._resolve_id(document_type, "/api/document_types/")
                if doc_type_id:
                    data["document_type"] = str(doc_type_id)
        
        # Resolve correspondent: if not numeric, try to find by name
        if correspondent:
            if correspondent.isdigit():
                data["correspondent"] = correspondent
            else:
                corr_id = await self._resolve_id(correspondent, "/api/correspondents/")
                if corr_id:
                    data["correspondent"] = str(corr_id)
        
        # Resolve tags: accept comma-separated names or IDs
        if tags:
            resolved_tag_ids = []
            for tag in tags:
                tag = tag.strip()
                if tag.isdigit():
                    resolved_tag_ids.append(tag)
                else:
                    tag_id = await self._resolve_id(tag, "/api/tags/")
                    if tag_id:
                        resolved_tag_ids.append(str(tag_id))
            if resolved_tag_ids:
                data["tags"] = ",".join(resolved_tag_ids)
        
        url = "/api/documents/post_document/"
        resp = await self._client.post(url, files=files, data=data)
        if resp.status_code >= 400:
            # include a short snippet for diagnostics
            txt = resp.text[:500]
            raise RuntimeError(f"paperless upload failed: {resp.status_code} {txt}")
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        if isinstance(payload, int):
            return {"id": payload}
        if isinstance(payload, str):
            return {"task_id": payload}
        if isinstance(payload, dict):
            return payload
        return {"task_id": None}

    async def get_task(self, task_id: str) -> dict | None:
        if task_id.isdigit():
            resp = await self._client.get(f"/api/tasks/{task_id}/")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            payload = resp.json()
            if isinstance(payload, dict):
                return payload
            return None

        resp = await self._client.get("/api/tasks/", params={"task_id": task_id})
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, dict):
            if isinstance(payload.get("results"), list):
                return payload["results"][0] if payload["results"] else None
            return payload
        if isinstance(payload, list):
            return payload[0] if payload else None
        return None

    def extract_task_id(self, payload: dict | None) -> str | None:
        if isinstance(payload, int):
            return str(payload)
        if isinstance(payload, str) and payload.strip():
            return payload.strip()
        if not isinstance(payload, dict):
            return None
        for key in ("task_id", "task", "uuid"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        task_row_id = payload.get("id")
        if isinstance(task_row_id, int):
            return str(task_row_id)
        if isinstance(task_row_id, str) and task_row_id.strip():
            return task_row_id.strip()
        return None

    def _extract_document_id(self, payload: dict | None) -> str | None:
        if not isinstance(payload, dict):
            return None
        candidates = [
            payload.get("related_document"),
            payload.get("document_id"),
            payload.get("paperless_id"),
            payload.get("id"),
        ]
        result = payload.get("result")
        if isinstance(result, dict):
            candidates.extend([result.get("document_id"), result.get("related_document"), result.get("id")])
        else:
            candidates.append(result)
        for candidate in candidates:
            if candidate is None:
                continue
            if isinstance(candidate, int):
                return str(candidate)
            if isinstance(candidate, str) and candidate.strip():
                trimmed = candidate.strip()
                if trimmed.isdigit():
                    return trimmed
        return None

    async def resolve_task(self, task_id: str) -> dict:
        task = await self.get_task(task_id)
        if task is None:
            return {"status": "processing", "document_id": None}

        document_id = self._extract_document_id(task)
        if document_id:
            return {"status": "ready", "document_id": document_id}

        raw_status = str(task.get("status") or task.get("state") or "").strip().lower()
        if raw_status in {"failure", "failed", "error", "cancelled", "canceled"}:
            return {"status": "failed", "document_id": None}
        return {"status": "processing", "document_id": None}

    async def wait_for_document(self, task_id: str, *, attempts: int = 8, delay_seconds: float = 0.5) -> dict:
        last_state = {"status": "processing", "document_id": None}
        for _ in range(attempts):
            last_state = await self.resolve_task(task_id)
            if last_state["status"] != "processing":
                return last_state
            await asyncio.sleep(delay_seconds)
        return last_state

    async def fetch_preview(self, document_id: str) -> tuple[bytes, str, str | None]:
        resp = await self._client.get(f"/api/documents/{document_id}/preview/")
        if resp.status_code >= 400:
            txt = resp.text[:500]
            raise RuntimeError(f"paperless preview failed: {resp.status_code} {txt}")
        return resp.content, resp.headers.get("content-type", "application/pdf"), resp.headers.get("content-disposition")

    async def fetch_download(self, document_id: str, *, original: bool = False) -> tuple[bytes, str, str | None]:
        resp = await self._client.get(
            f"/api/documents/{document_id}/download/",
            params={"original": "true"} if original else None,
        )
        if resp.status_code >= 400:
            txt = resp.text[:500]
            raise RuntimeError(f"paperless download failed: {resp.status_code} {txt}")
        return resp.content, resp.headers.get("content-type", "application/octet-stream"), resp.headers.get("content-disposition")

    async def fetch_document(self, document_id: str) -> dict:
        resp = await self._client.get(f"/api/documents/{document_id}/")
        if resp.status_code >= 400:
            txt = resp.text[:500]
            raise RuntimeError(f"paperless document fetch failed: {resp.status_code} {txt}")
        return resp.json()

    async def fetch_document_type(self, document_type_id: int | str) -> dict:
        resp = await self._client.get(f"/api/document_types/{document_type_id}/")
        if resp.status_code >= 400:
            txt = resp.text[:500]
            raise RuntimeError(f"paperless document type fetch failed: {resp.status_code} {txt}")
        return resp.json()

    @staticmethod
    def extract_document_metadata(payload: dict | None, *, document_type_name: str | None = None) -> dict:
        if not isinstance(payload, dict):
            return {
                "title": None,
                "document_date": None,
                "document_type": document_type_name,
            }

        raw_date = payload.get("created") or payload.get("created_date") or payload.get("document_date") or payload.get("added")
        normalized_date: date | None = None
        if isinstance(raw_date, str) and raw_date:
            try:
                normalized_date = parse_date_value(raw_date[:10])
            except Exception:
                normalized_date = None

        return {
            "title": payload.get("title"),
            "document_date": normalized_date,
            "document_type": document_type_name,
        }

    async def fetch_document_metadata(self, document_id: str) -> dict:
        payload = await self.fetch_document(document_id)
        document_type_name = None
        document_type_id = payload.get("document_type")
        if document_type_id not in (None, ""):
            try:
                document_type = await self.fetch_document_type(document_type_id)
                if isinstance(document_type, dict):
                    document_type_name = document_type.get("name")
            except Exception:
                document_type_name = None
        return self.extract_document_metadata(payload, document_type_name=document_type_name)
