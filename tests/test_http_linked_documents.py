"""Linked document routes with a fake Paperless adapter."""

from __future__ import annotations

import base64
import unittest

from tests.support import asgi_test_client, temporary_database


class FakePaperless:
    def __init__(self) -> None:
        self.uploads: list[bytes] = []

    def check_reachability(self, base_url: str, token: str) -> tuple[bool, str]:
        return True, "Paperless reachable"

    def upload_document(
        self, base_url: str, token: str, filename: str, content_type: str, content_blob: bytes
    ) -> dict:
        self.uploads.append(content_blob)
        return {
            "paperless_document_id": "7002", "paperless_task_id": None,
            "paperless_reference_url": base_url + "/documents/7002/details/",
            "upload_status": "paperless_uploaded", "upload_error": None,
        }

    def download_document(
        self, base_url: str, token: str, paperless_document_id: str, fallback_filename: str
    ) -> dict:
        return {
            "filename": fallback_filename, "content_type": "text/plain",
            "content_blob": b"document bytes",
        }


class LinkedDocumentsHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = self.enterContext(temporary_database(seeded=True))
        self.paperless = FakePaperless()
        self.client = asgi_test_client(self.database, paperless=self.paperless)
        configured = self.client.put("/api/v1/settings/paperless", json={
            "base_url": "https://paperless.example.test", "api_token": "test-token",
        })
        self.assertEqual(configured.status_code, 200, configured.text)

    def test_status_and_document_links_for_each_owner(self) -> None:
        status = self.client.get("/api/v1/paperless/status")
        self.assertEqual(status.status_code, 200, status.text)
        self.assertTrue(status.json()["reachable"])
        for owner in ("expenses", "tenants", "leases"):
            with self.subTest(owner=owner):
                path = f"/api/v1/{owner}/1/documents"
                created = self.client.post(path, json={
                    "documents": [{"paperless_document_id": "4711", "filename": "linked.pdf"}],
                })
                self.assertEqual(created.status_code, 201, created.text)
                document = created.json()["documents"][0]
                self.assertEqual(document["paperless_document_id"], "4711")
                document_id = document["id"]
                listed = self.client.get(path)
                self.assertEqual(listed.status_code, 200, listed.text)
                self.assertEqual(listed.json()["documents"][-1]["id"], document_id)
                downloaded = self.client.get(f"{path}/{document_id}/download")
                self.assertEqual(downloaded.status_code, 200, downloaded.text)
                self.assertEqual(downloaded.content, b"document bytes")
                self.assertIn("linked.pdf", downloaded.headers["content-disposition"])
                deleted = self.client.delete(f"{path}/{document_id}")
                self.assertEqual(deleted.status_code, 200, deleted.text)
                self.assertTrue(deleted.json()["deleted"])

    def test_upload_and_invalid_owner_document_are_handled(self) -> None:
        path = "/api/v1/tenants/1/documents"
        uploaded = self.client.post(path, json={
            "documents": [{
                "filename": "passport.txt", "content_type": "text/plain",
                "content_base64": base64.b64encode(b"passport").decode("ascii"),
            }],
        })
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        self.assertEqual(self.paperless.uploads, [b"passport"])
        self.assertEqual(uploaded.json()["documents"][0]["upload_status"], "paperless_uploaded")
        missing = self.client.get("/api/v1/tenants/999/documents")
        self.assertEqual(missing.status_code, 422)
        self.assertEqual(missing.json()["error"]["code"], "invalid_value")


if __name__ == "__main__":
    unittest.main()
