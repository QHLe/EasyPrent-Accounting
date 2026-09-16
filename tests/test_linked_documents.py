from __future__ import annotations

import base64
import unittest

from easyprent_accounting.linked_documents import LinkedDocuments, get_paperless_status
from tests.support import in_memory_database


class FakePaperless:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str, str, str, bytes]] = []
        self.downloads: list[tuple[str, str, str, str]] = []

    def check_reachability(self, base_url: str, token: str) -> tuple[bool, str]:
        return True, "Paperless Server erreichbar."

    def upload_document(
        self,
        base_url: str,
        token: str,
        filename: str,
        content_type: str,
        content_blob: bytes,
    ) -> dict:
        self.uploads.append((base_url, token, filename, content_type, content_blob))
        return {
            "upload_status": "paperless_uploaded",
            "paperless_document_id": "7002",
            "paperless_task_id": None,
            "paperless_reference_url": base_url + "/documents/7002/details/",
            "upload_error": None,
        }

    def download_document(
        self,
        base_url: str,
        token: str,
        paperless_document_id: str,
        fallback_filename: str,
    ) -> dict:
        self.downloads.append(
            (base_url, token, paperless_document_id, fallback_filename)
        )
        return {
            "filename": fallback_filename,
            "content_type": "text/plain",
            "content_blob": b"Passdaten",
        }


class LinkedDocumentsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = in_memory_database()
        self.connection.execute(
            """INSERT INTO paperless_settings
               (base_url, api_token, created_at, updated_at)
               VALUES (?, ?, ?, ?)""",
            (
                "https://paperless.example.org",
                "test-token",
                "2025-01-01T00:00:00+00:00",
                "2025-01-01T00:00:00+00:00",
            ),
        )
        self.connection.commit()
        self.paperless = FakePaperless()
        self.documents = LinkedDocuments(self.connection, self.paperless)

    def tearDown(self) -> None:
        self.connection.close()

    def test_tenant_upload_uses_injected_paperless_and_lists_link(self) -> None:
        uploaded = self.documents.add(
            "tenant",
            1,
            {
                "documents": [
                    {
                        "filename": "passport.txt",
                        "content_type": "text/plain",
                        "content_base64": base64.b64encode(b"Passdaten").decode("ascii"),
                    }
                ]
            },
        )

        self.assertEqual(
            self.paperless.uploads,
            [
                (
                    "https://paperless.example.org",
                    "test-token",
                    "passport.txt",
                    "text/plain",
                    b"Passdaten",
                )
            ],
        )
        self.assertEqual(uploaded["documents"][0]["paperless_document_id"], "7002")
        self.assertEqual(
            self.documents.list("tenant", 1)["documents"], uploaded["documents"]
        )

    def test_expense_link_downloads_through_fake_and_caller_controls_rollback(self) -> None:
        before = self.documents.list("expense", 1)["documents"]
        linked = self.documents.add(
            "expense", 1, {"documents": [{"paperless_document_id": "9001"}]}
        )
        document = linked["documents"][0]

        self.assertEqual(document["upload_status"], "paperless_linked")
        self.assertEqual(self.paperless.uploads, [])
        self.assertEqual(
            self.documents.download("expense", 1, document["id"])["content_blob"],
            b"Passdaten",
        )
        self.assertEqual(
            self.paperless.downloads,
            [("https://paperless.example.org", "test-token", "9001", "paperless-document-9001")],
        )

        self.connection.rollback()
        self.assertEqual(self.documents.list("expense", 1)["documents"], before)

    def test_status_uses_injected_adapter(self) -> None:
        status = get_paperless_status(self.connection, self.paperless)

        self.assertTrue(status["configured"])
        self.assertTrue(status["reachable"])
        self.assertEqual(status["message"], "Paperless Server erreichbar.")

    def test_archived_expense_cannot_change_its_document_links(self) -> None:
        linked = self.documents.add(
            "expense", 1, {"documents": [{"paperless_document_id": "9001"}]}
        )
        document_id = linked["documents"][0]["id"]
        self.connection.execute("UPDATE expense_items SET is_archived = 1 WHERE id = 1")

        with self.assertRaisesRegex(ValueError, "archived expenses cannot be edited"):
            self.documents.add(
                "expense", 1, {"documents": [{"paperless_document_id": "9002"}]}
            )
        with self.assertRaisesRegex(ValueError, "archived expenses cannot be edited"):
            self.documents.delete("expense", 1, document_id)

        self.assertEqual(len(self.documents.list("expense", 1)["documents"]), 1)

    def test_lease_document_link_can_be_deleted_without_paperless_delete(self) -> None:
        linked = self.documents.add(
            "lease", 1, {"documents": [{"paperless_document_id": "9001"}]}
        )
        document_id = linked["documents"][0]["id"]

        self.assertEqual(linked["resource_type"], "lease")
        self.assertEqual(linked["documents"][0]["resource_id"], 1)
        self.assertTrue(self.documents.delete("lease", 1, document_id)["deleted"])
        self.assertEqual(self.documents.list("lease", 1)["documents"], [])
        self.assertEqual(self.paperless.uploads, [])
        self.assertEqual(self.paperless.downloads, [])


if __name__ == "__main__":
    unittest.main()
